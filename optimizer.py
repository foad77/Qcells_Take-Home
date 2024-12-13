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
        self.battery_capacity = 53.0  # kWh max
        self.max_power = 25.0         # kW
        self.eta_charge = 0.95
        self.eta_discharge = 0.95

        # Will be set in build_model()
        self.p_charge = None
        self.p_discharge = None
        self.soc = None
        self.meter_positive = None
        self.meter_negative = None
        self.M = None
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
        self.soc = cp.Variable(self.T+1)
        self.meter_positive = cp.Variable(self.T, nonneg=True)
        self.meter_negative = cp.Variable(self.T, nonneg=True)
        self.M = cp.Variable(nonneg=True)

        constraints = []

        # Initial condition
        constraints += [self.soc[0] == 0]

        # Battery dynamics and constraints
        for t in range(self.T):
            constraints += [
                self.soc[t+1] == self.soc[t] + self.p_charge[t]*self.eta_charge - self.p_discharge[t]/self.eta_discharge,
                self.soc[t+1] <= self.battery_capacity,
                self.soc[t+1] >= 0
            ]

        # Power limits
        constraints += [
            self.p_charge <= self.max_power,
            self.p_discharge <= self.max_power
        ]

        # Battery cannot charge more than PV at any time
        for t in range(self.T):
            constraints += [self.p_charge[t] <= self.pv_data[t]]

        # Meter definition:
        # meter(t) = load(t) - pv(t) + p_charge(t) - p_discharge(t)
        # meter(t) = meter_positive(t) - meter_negative(t)
        for t in range(self.T):
            lhs = self.load_data[t] - self.pv_data[t] + self.p_charge[t] - self.p_discharge[t]
            constraints += [lhs == self.meter_positive[t] - self.meter_negative[t]]

        # Demand charge constraint: M >= meter_positive(t) during demand window
        for t in range(self.T):
            if in_demand_window[t]:
                constraints += [self.M >= self.meter_positive[t]]

        # Objective function
        import_cost = self.prices['import_cost'] * cp.sum(self.meter_positive)

        # Export revenue:
        # Base export revenue: export_revenue, add demand_response_revenue in DR window
        export_revenue_array = np.full(self.T, self.prices['export_revenue'])
        export_revenue_array[in_dr_window] += self.prices['demand_response_revenue']

        export_revenue_term = cp.sum(cp.multiply(export_revenue_array, self.meter_negative))

        # Demand charge
        demand_charge_cost = self.prices['demand_charge'] * self.M

        # Objective: minimize import_cost + demand_charge - export_revenue
        objective = cp.Minimize(import_cost + demand_charge_cost - export_revenue_term)

        self.prob = cp.Problem(objective, constraints)

    def solve(self):
        self.prob.solve(solver=cp.OSQP, verbose=False)

        if self.prob.status not in ["infeasible", "unbounded"]:
            p_charge_val = self.p_charge.value
            p_discharge_val = self.p_discharge.value
            meter_positive_val = self.meter_positive.value
            meter_negative_val = self.meter_negative.value

            battery_power_val = p_charge_val - p_discharge_val
            meter_val = meter_positive_val - meter_negative_val

            return {
                'battery_power': battery_power_val,
                'meter': meter_val
            }
        else:
            raise ValueError("Problem not solvable. Status: " + self.prob.status)
