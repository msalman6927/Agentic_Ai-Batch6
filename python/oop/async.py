
from time import time
import asyncio


async def fetch_data():
    print("Fetching data...")
    await asyncio.sleep(5)
    print("Data fetched successfully.")    #coroutine function

async def inform_administrator():
    print("informing administrator...")
    await asyncio.sleep(5)
    print("Administrator informed.")


async def main():
    response=await asyncio.gather(fetch_data(), inform_administrator())
    
    return response

asyncio.run(main())

def call_database():
    print("Calling database...")
    time.sleep(3)
    print("Data received from database.")
    
    

    
    
    
    
    