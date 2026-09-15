"""Trusted, local provisioning for non-student accounts.

Run from the backend service host; this module intentionally exposes no HTTP
endpoint and reads a password without echoing it to the terminal.

Commands:
  create-teacher <username>   provision a teacher with a linked teacher record
  create-admin <username>     provision an administrator
  rotate-password <username>  replace a password (reads it from stdin, never argv)
  audit-accounts              list accounts and flag risky leftovers (no hashes)
  delete-user <username>      remove an account that nothing references
"""
import argparse
import getpass
import sys

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Teacher, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a ClinPath staff account")
    parser.add_argument(
        "command",
        choices=["create-teacher", "create-admin", "rotate-password", "audit-accounts", "delete-user"],
    )
    parser.add_argument("username", nargs="?")
    parser.add_argument("--name")
    parser.add_argument("--teacher-no")
    parser.add_argument("--department", default="临床教学")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "audit-accounts":
            _audit_accounts(db)
            return
        if not args.username:
            raise SystemExit(f"{args.command} requires a username")
        if args.command == "delete-user":
            _delete_user(db, args.username)
            return
        if args.command == "rotate-password":
            _rotate_password(db, args.username)
            return

        password = _read_password()
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


def _read_password() -> str:
    """Read a password without echoing it and without putting it in argv."""

    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Repeat: ")
        if password != confirm:
            raise SystemExit("Passwords do not match")
    else:
        password = sys.stdin.readline().rstrip("\n")
    if len(password) < 6:
        raise SystemExit("Password must be at least 6 characters")
    return password


def _rotate_password(db, username: str) -> None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise SystemExit("User not found")
    user.password_hash = hash_password(_read_password())
    db.commit()
    # Deliberately no password output.
    print(f"Rotated password for {user.username} ({user.role})")


def _delete_user(db, username: str) -> None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise SystemExit("User not found")
    from app.models import TeacherScoreReview

    referenced = (
        db.query(TeacherScoreReview).filter(TeacherScoreReview.reviewer_user_id == user.id).count()
    )
    if referenced:
        raise SystemExit(f"Refusing to delete: {referenced} score review(s) reference this user")
    if user.role == "admin":
        remaining = db.query(User).filter(User.role == "admin", User.id != user.id).count()
        if remaining == 0:
            raise SystemExit("Refusing to delete the last administrator")
    db.delete(user)
    db.commit()
    print(f"Deleted {user.username} ({user.role})")


def _audit_accounts(db) -> None:
    """List accounts for a security review. Never prints password material."""

    users = db.query(User).order_by(User.id).all()
    by_student: dict[int, list[str]] = {}
    for user in users:
        if user.student_id is not None:
            by_student.setdefault(user.student_id, []).append(user.username)

    print(f"{len(users)} account(s):")
    for user in users:
        flags: list[str] = []
        if user.role in {"teacher", "admin"} and user.username in {"teacher", "admin"}:
            # The name itself is fine; the flag is a reminder to confirm the
            # historical default password no longer works for it.
            flags.append("legacy-default-name:verify-password-rotated")
        if user.role == "admin" and user.teacher_id is None:
            flags.append("unlinked-admin")
        if user.teacher_id is not None and not db.get(Teacher, user.teacher_id):
            flags.append("missing-teacher-record")
        if user.student_id is not None and len(by_student.get(user.student_id, [])) > 1:
            flags.append("duplicate-student-login")
        suffix = f"  <-- {', '.join(flags)}" if flags else ""
        print(
            f"  {user.id:>3}  {user.username:<28} {user.role:<8}"
            f" student={user.student_id} teacher={user.teacher_id}{suffix}"
        )


if __name__ == "__main__":
    main()
