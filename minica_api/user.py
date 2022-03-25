"""Module for creating users and chowing certificates to them"""
from dataclasses import dataclass
from os import chown, getenv
from pathlib import Path
from subprocess import run

import inflect

inflection_engine = inflect.engine()


@dataclass
class User:
    uid: int
    gid: int
    username: str


def get_existing_users() -> list[User]:
    passwd_contents = Path("/etc/passwd").read_text()
    lines = passwd_contents.strip().splitlines(keepends=False)
    users = []
    for line in lines:
        username, _, uid, gid, *rest = line.split(":")
        users.append(User(int(uid), int(gid), username))
    return users


def create_user(user: User):
    gid_as_words = str(inflection_engine.number_to_words(user.gid))
    desired_group_name = f"group_{gid_as_words.replace(' ', '_')}"
    command = ["addgroup", "--gid", str(user.gid), desired_group_name]
    run(command)
    command = [
        "adduser",
        "--gecos",
        "",
        "--no-create-home",
        "--disabled-login",
        "--shell",
        "/usr/sbin/nologin",
        "--uid",
        str(user.uid),
        "--gid",
        str(user.gid),
        user.username,
    ]
    proc = run(command)
    if proc.returncode > 0:
        raise Exception(f"Couldn't create desired user {user}")


def get_user() -> User:
    desired_uid = int(getenv("USER_ID", 0))
    desired_gid = int(getenv("GROUP_ID", 0))
    id_as_words = str(inflection_engine.number_to_words(desired_uid))
    existing_users = get_existing_users()

    try:
        existing_user = next(u for u in existing_users if u.uid == desired_uid)
        return existing_user
    except StopIteration:
        desired_username = f"user_{id_as_words.replace(' ', '_')}"
        user = User(desired_uid, desired_gid, desired_username)
        create_user(user)
        return user


def donate_certificates(certificates: list[Path], to_user: User):
    for certificate in certificates:
        chown(certificate, to_user.uid, to_user.gid)
