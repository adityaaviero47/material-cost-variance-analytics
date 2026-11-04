"""Download the USAID SCMS Delivery History dataset and write the compressed copy the analysis reads.
Only needed if data/ is empty:  python get_data.py"""
import os, pandas as pd

# public GitHub mirror of the dataset published by USAID (Supply Chain Shipment Pricing Data)
URL = "https://raw.githubusercontent.com/satoshi-f13/usaid-scms-dashboard/4680a82f27695907892f61f92dade17e05ec15b4/data/SCMS_Delivery_History_Dataset.csv"

def build(src=URL):
    d = pd.read_csv(src, encoding="latin1")
    d.columns = [c.replace("ï»¿", "").replace("﻿", "") for c in d.columns]
    os.makedirs("data", exist_ok=True)
    d.to_csv("data/SCMS_Delivery_History_Dataset.csv.gz", index=False, compression="gzip")
    print(f"data/SCMS_Delivery_History_Dataset.csv.gz  {len(d):,} rows")

if __name__ == "__main__":
    build()
