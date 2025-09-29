from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.db_models import ControllerJob
from db_utils import update_job_status
from config import SQLALCHEMY_DATABASE_URL

def main():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    all_jobs = session.query(ControllerJob).all()
    print(f"Found {len(all_jobs)} jobs to update.")

    patched_count = 0
    for job in all_jobs:
        old_status = job.status
        update_job_status(session, job.id)
        if job.status != old_status:
            print(f"Job {job.id}: {old_status} -> {job.status}")
            patched_count += 1

    session.commit()
    print(f"Patched {patched_count} jobs.")

if __name__ == "__main__":
    main()