# pull_spy_ats.py
# pulls weekly ATS (dark pool) trading data for SPY from FINRA. 

# import pys module to interact w os to read env variables
import os
# lib for making HTTP req
import requests
import pandas as pd
from io import StringIO
from dotenv import load_dotenv

# read the .env file in the current folder.
load_dotenv()

#read client id/ secret from env
CLIENT_ID = os.getenv("FINRA_CLIENT_ID")
CLIENT_SECRET = os.getenv("FINRA_CLIENT_SECRET")

# ---- STEP 1: GET AN ACCESS TOKEN ----
# get acess token for OAuth2 from FRINA endpoint
auth_url = "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token"

# make the actual auth request to FINRA
auth_response = requests.post(
    auth_url,                                    
    auth=(CLIENT_ID, CLIENT_SECRET),             
    params={"grant_type": "client_credentials"} 
)

# extract token string from FINRA's JSON response
access_token = auth_response.json()["access_token"]
#  need this token to authenticate every data request that follows

# status message to check
print("Authenticated.")


# pull ATS data

# FINRA's Weekly Summary endpoint 
data_url = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"

# HTTP headers sent with every data request
headers = {
    "Authorization": f"Bearer {access_token}",  
    "Accept": "text/plain",                    
}

# list that will accumulate DataFrames as we split the data sets from FINRAs rate limiting
all_rows = []
# track which row we're starting from
# increment this by batch_size after each request
offset = 0

batch_size = 100


# keep requesting batches until FINRA stops giving data

while True:
    # break out when there's no more data to fetch.
    
    # Python dict describing the request we want to make
    # filter on ticker and record type
    params = {
        "limit": batch_size,   
        "offset": offset,       
        "compareFilters": [  
            {
                "fieldName": "issueSymbolIdentifier",  
                "fieldValue": "SPY",                  
                "compareType": "EQUAL"                
            },
            {
                "fieldName": "summaryTypeCode",   
                "fieldValue": "ATS_W_SMBL",         
                "compareType": "EQUAL"
            },
        ],
    }

    # data request to FINRA.
    response = requests.post(data_url, headers=headers, json=params)
    # fetch one batch of rows.

    if response.status_code != 200:
        # check if the request failed (HTTP 200 = success)
        print(f"Error at offset {offset}: {response.status_code}")
        print(response.text[:300]) 
        break 

    text = response.text.strip()
    # get response body as text, leading/trailing whitespace removed
    
    if not text:
        # if the response is empty, done
        print("Done — no more data.")
        break

    if offset == 0:
        df = pd.read_csv(StringIO(text))
        # parse the first batch's CSV (with column headers) into a DataFrame
    else:
        df = pd.read_csv(StringIO(text), header=None, names=all_rows[0].columns)
        # parse subsequent batches (no headers), the column names from the first batch

    if len(df) == 0:
        break

    all_rows.append(df)
    # add  batch's DataFrame to list of batches


    if len(df) < batch_size:
        print("Done — last batch.")
        break

    offset += batch_size
    # move the offset forward for the next request


# combine data and finish

if all_rows:
    full_df = pd.concat(all_rows, ignore_index=True)
    # stack all batch DataFrames into one big DataFrame

    # clean the data

    full_df = full_df[full_df["issueSymbolIdentifier"] != "issueSymbolIdentifier"]
    # remove any row where  ticker col contains "issueSymbolIdentifier"

    numeric_cols = ["totalWeeklyTradeCount", "totalWeeklyShareQuantity", "totalNotionalSum"]

    for col in numeric_cols:
        full_df[col] = pd.to_numeric(full_df[col], errors="coerce")
        # convert each column from text to numbers

    full_df["weekStartDate"] = pd.to_datetime(full_df["weekStartDate"])
    # convert weekStartDate column from text to actual datetime object

    full_df = full_df.sort_values("weekStartDate").reset_index(drop=True)
    # sort  rows chronologically and renumber the index


    full_df.to_csv("spy_ats_data.csv", index=False)
    # save cleaned, typed DataFrame to disk

    print(f"\nTotal rows: {len(full_df)}")
    print(f"Saved to spy_ats_data.csv")
    print(f"Date range: {full_df['weekStartDate'].min().date()} to {full_df['weekStartDate'].max().date()}")
    print(f"Mean weekly ATS volume: {full_df['totalWeeklyShareQuantity'].mean():,.0f} shares")

else:
    print("No data returned. Check filters or credentials.")
