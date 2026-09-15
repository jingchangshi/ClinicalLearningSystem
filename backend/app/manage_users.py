"""Trusted, local provisioning for non-student accounts.

Run from the backend service host; this module intentionally exposes no HTTP
endpoint and reads a password without echoing it to the terminal.
"""
import argparse
import getpass
import sys

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Teacher, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a ClinPath staff account")
    parser.add_argument("command", choices=["create-teacher", "create-admin"])
    parser.add_argument("username")
    parser.add_argument("--name")
    parser.add_argument("--teacher-no")
    parser.add_argument("--department", default="临床教学")
    args = parser.parse_args()
    password = getpass.getpass("Password: ")
    if len(password) < 6:
        raise SystemExit("Password must be at least 6 characters")

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == args.username).first():
            raise SystemExit("Username already exists")
        if args.command == "create-teacher":
            if not args.teacher_no:
                raise SystemExit("--teacher-no is required for teachers")
            if db.query(Teacher).filter(Teacher.teacher_no == args.teacher_no).first():
                raise SystemExit("Teacher number already exists")
            teacher = Teacher(
                name=args.name or args.username,
                teacher_no=args.teacher_no,
                department=args.department,
            )
            db.add(teacher)
            db.flush()
            user = User(username=args.username, password_hash=hash_password(password), role="teacher", teacher_id=teacher.id)
        else:
            user = User(username=args.username, password_hash=hash_password(password), role="admin")
        db.add(user)
        db.commit()
        print(f"Created {user.role} account for {user.username}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
