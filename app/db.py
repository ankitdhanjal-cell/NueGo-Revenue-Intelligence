"""Database connection, shared by the API and the pipeline scripts."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
