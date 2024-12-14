# main.py
import pandas as pd
from optimizer import Optimizer

def run_optimization():
    # Load data
    df = pd.read_csv('data/profiles.csv', parse_dates=['Time'],date_parser=lambda x: pd.to_datetime(x, format='%m/%d/%y %H:%M'))
    
    # Extract load and PV data
    load_data = df['Load (kW)'].values
    pv_data = df['PV (kW)'].values
    time_index = df['Time']
    
    # Define pricing and other parameters (example values)
    prices = {
        'import_cost': 0.1,
        'export_revenue': 0.03,
        'demand_charge': 9.0,
        'demand_response_revenue': 10.0,
        'demand_charge_start': '17:00',
        'demand_charge_end': '21:00',
        'demand_response_start': '19:00',
        'demand_response_end': '20:00'
    }
    
    # Instantiate and run the optimizer
    optimizer = Optimizer(load_data, pv_data, prices)
    optimizer.build_model(time_index)
    solution = optimizer.solve()  # Suppose this returns a dict or dataframe with Time, AC Battery Power, Meter
    
    # Write results
    results = pd.DataFrame({
        'Time': time_index,
        'AC Battery Power (kW)': solution['battery_power'],
        'Meter (kW)': solution['meter']
    })
    results.to_csv('data/results.csv', index=False)

if __name__ == "__main__":
    run_optimization()
