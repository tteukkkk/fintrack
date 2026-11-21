import os
import uvicorn
from fintrack.app import app
if __name__=='__main__': uvicorn.run(app,host=os.environ.get('FINTRACK_HOST','127.0.0.1'),port=int(os.environ.get('FINTRACK_PORT','8020')))
