import httpx
from time import time
import asyncio


async def fetch_data(clients,number):
    async with httpx.AsyncClient() as client:
        response=await client.get("https://jsonplaceholder.typicode.com/todos/1")
        return response.json()
    
async def main():
    start_time=time()
    data=await fetch_data()
    end_time=time()
    print(f"Data: {data}, Time taken: {end_time - start_time:.2f} seconds")
    
asyncio.run(main())