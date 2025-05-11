from agent_blue import get_role_by_email

if __name__ == "__main__":
    # Test-E-Mails (bitte ggf. anpassen)
    test_emails = [
        "admin@neckattack.net",
        "kunde1@firma.de",
        "masseur123@neckattack.net",
        "unbekannt@beispiel.de"
    ]
    for email in test_emails:
        role = get_role_by_email(email)
        print(f"{email}: {role}")
