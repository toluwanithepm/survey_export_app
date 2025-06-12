from dotenv import load_dotenv
import os

load_dotenv()  # this loads the variables from .env

database_url = os.getenv("DATABASE_URL")

print("Database URL:", database_url)
