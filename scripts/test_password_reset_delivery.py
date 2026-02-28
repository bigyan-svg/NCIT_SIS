import argparse
import os
import sys

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import generate_numeric_otp, send_password_reset_email, send_password_reset_sms

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Send test password-reset OTP via configured email/SMS providers."
    )
    parser.add_argument("--email", help="Target email address for SMTP test")
    parser.add_argument("--phone", help="Target phone number for Twilio SMS test (E.164 recommended)")
    parser.add_argument("--otp", help="Optional OTP code to send (defaults to generated digits)")
    args = parser.parse_args()

    if not args.email and not args.phone:
        parser.error("Provide at least one target: --email and/or --phone")

    otp_length = int(os.getenv("PWD_RESET_OTP_LENGTH", "6") or "6")
    otp_code = (args.otp or "").strip() or generate_numeric_otp(otp_length)
    print(f"Using OTP code: {otp_code}")

    checks = []
    if args.email:
        checks.append(("email", args.email.strip(), send_password_reset_email))
    if args.phone:
        checks.append(("phone", args.phone.strip(), send_password_reset_sms))

    failed = 0
    for channel, destination, sender in checks:
        sent, error = sender(destination, otp_code)
        if sent:
            print(f"[OK] {channel}: delivered to {destination}")
        else:
            failed += 1
            print(f"[FAIL] {channel}: {error or 'unknown error'}")

    if failed:
        sys.exit(1)
    print("All requested delivery checks passed.")


if __name__ == "__main__":
    main()
