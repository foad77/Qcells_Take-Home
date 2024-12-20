# optimizer.py
import cvxpy as cp
import numpy as np
import pandas as pd

class Optimizer:
    def __init__(self, load_data, pv_data, prices):
        """
        Parameters:
        - load_data: array of load values (kW)
        - pv_data: array of PV values (kW)
        - prices: dictionary with keys:
            'import_cost': float, e.g. 0.1 ($/kWh)
            'export_revenue': float, e.g. 0.03 ($/kWh)
            'demand_charge': float, e.g. 9.0 ($/kW)
            'demand_response_revenue': float, e.g. 10.0 ($/kWh)
            'demand_charge_start': str, e.g. '17:00' (5pm)
            'demand_charge_end': str, e.g. '21:00'   (9pm)
            'demand_response_start': str, '19:00' (7pm)
            'demand_response_end': str, '20:00'   (8pm)
        """
        self.load_data = load_data
        self.pv_data = pv_data
        self.prices = prices

        # Basic parameters
        self.T = len(load_data)
        self.battery_capacity = 53.0   # kWh max
        self.max_power = 25.0          # kW
        self.eta_charge = 0.95
        self.eta_discharge = 0.95

        # Set time step duration (Δt) based on your data frequency
        # For example, if data is in 30-minute increments:
        self.delta_t = 0.5  # hours per time step

        # Will be set in build_model()
        self.p_charge = None
        self.p_discharge = None
        self.p_gridimport = None
        self.p_gridexport = None
        self.soc = None
        self.M = None
        self.y = None   # binary variables
        self.prob = None

    def build_model(self, time_index):
        """
        Build the optimization model.

        Parameters:
        - time_index: pandas Series of timestamps corresponding to each timestep.
        """

        # Convert times to just time-of-day for comparisons
        time_of_day = time_index.dt.time

        # Create boolean masks for the windows
        demand_charge_start = pd.to_datetime(self.prices['demand_charge_start']).time()
        demand_charge_end = pd.to_datetime(self.prices['demand_charge_end']).time()
        in_demand_window = (time_of_day >= demand_charge_start) & (time_of_day < demand_charge_end)

        demand_response_start = pd.to_datetime(self.prices['demand_response_start']).time()
        demand_response_end = pd.to_datetime(self.prices['demand_response_end']).time()
        in_dr_window = (time_of_day >= demand_response_start) & (time_of_day < demand_response_end)

        # Decision variables
        self.p_charge = cp.Variable(self.T, nonneg=True)
        self.p_discharge = cp.Variable(self.T, nonneg=True)
        self.p_gridimport = cp.Variable(self.T, nonneg=True)
        self.p_gridexport = cp.Variable(self.T, nonneg=True)
        self.soc = cp.Variable(self.T+1)
        self.M = cp.Variable(nonneg=True)

        # Binary variables for mode selection at each time step
        self.y = cp.Variable(self.T, boolean=True)

        constraints = []

        # Initial and final SOC conditions
        constraints += [self.soc[0] == 0]

        # Battery SOC dynamics
        for t in range(self.T):
            constraints += [
                self.soc[t+1] == self.soc[t] 
                                  + self.eta_charge * self.p_charge[t] * self.delta_t
                                  - (self.p_discharge[t] * self.delta_t / self.eta_discharge),
                self.soc[t+1] <= self.battery_capacity,
                self.soc[t+1] >= 0
            ]

        # End with empty battery
        constraints += [self.soc[self.T] == 0]

        # Battery power limits
        constraints += [
            self.p_charge <= self.max_power,
            self.p_discharge <= self.max_power
        ]

        # Battery charging cannot exceed PV
        for t in range(self.T):
            constraints += [self.p_charge[t] <= self.pv_data[t]]

        # Power balance at the meter:
        for t in range(self.T):
            lhs = self.load_data[t] - self.pv_data[t] + self.p_charge[t] - self.p_discharge[t]
            constraints += [self.p_gridimport[t] - self.p_gridexport[t] == lhs]

        # Demand charge constraint:
        for t in range(self.T):
            if in_demand_window[t]:
                constraints += [self.M >= self.p_gridimport[t]]

        # Big-M constraints for import/export modes
        M_val = max(np.max(self.load_data), np.max(self.pv_data), self.max_power) * 10
        for t in range(self.T):
            constraints += [self.p_gridimport[t] <= M_val * self.y[t]]
            constraints += [self.p_gridexport[t] <= M_val * (1 - self.y[t])]

        # Objective function
        import_cost = self.prices['import_cost'] * cp.sum(self.p_gridimport * self.delta_t)
        export_revenue_array = np.full(self.T, self.prices['export_revenue'])
        export_revenue_array[in_dr_window] += self.prices['demand_response_revenue']
        export_revenue_term = cp.sum(cp.multiply(export_revenue_array, self.p_gridexport) * self.delta_t)
        demand_charge_cost = self.prices['demand_charge'] * self.M

        objective = cp.Minimize(import_cost + demand_charge_cost - export_revenue_term)

        self.prob = cp.Problem(objective, constraints)

    def solve(self):
        # XPRESS can handle MILP problems
        self.prob.solve(solver=cp.XPRESS, verbose=True)

        if self.prob.status not in ["infeasible", "unbounded"]:
            p_charge_val = np.round(self.p_charge.value, 3)
            p_discharge_val = np.round(self.p_discharge.value, 3)
            p_gridimport_val = np.round(self.p_gridimport.value, 3)
            p_gridexport_val = np.round(self.p_gridexport.value, 3)

            # Battery power = p_discharge - p_charge
            battery_power_val = np.round(p_discharge_val - p_charge_val, 3)
            # Meter = p_gridimport - p_gridexport
            meter_val = np.round(p_gridimport_val - p_gridexport_val, 3)

            return {
                'battery_power': battery_power_val,
                'meter': meter_val
            }
        else:
            raise ValueError("Problem not solvable. Status: " + self.prob.status)
