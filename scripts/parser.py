#!/usr/bin/python3
import pandas as pd
import sys

def parse_csv(csv_input):
    df = pd.read_csv(csv_input)
    df['_time'] = pd.to_datetime(df['_time'], format='%Y-%m-%dT%H:%M:%S.%fZ', errors='coerce')
    df['_time'] = df['_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
    
    pivoted_df = df.pivot_table(index=['_time', 'rtue_data_id'], columns='_field', values='_value', aggfunc='first')
    pivoted_df.reset_index(inplace=True)
    columns = ['_time', 'rtue_data_id'] + [col for col in pivoted_df.columns if col not in ['_time', 'rtue_data_id']]
    pivoted_df = pivoted_df[columns]
    pivoted_df = pivoted_df.fillna('')
    
    return pivoted_df

def save_to_csv(df, csv_output):
    df.to_csv(csv_output, index=False, sep='\t')

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 parser.py {csv_input} {csv_output}")
        sys.exit(1)

    csv_input = sys.argv[1]
    csv_output = sys.argv[2]

    parsed_data = parse_csv(csv_input)
    save_to_csv(parsed_data, csv_output)
    print(f"Data has been saved to {csv_output}")
