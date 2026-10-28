# Encrypted Railway credentials

The Django app is `railway_autoscaler`.

## Host project setup

Add the app to the host project's settings:

```python
INSTALLED_APPS = [
    # ...
    "railway_autoscaler",
]

RAILWAY_AUTOSCALER_CREDENTIAL_KEY = os.environ["RAILWAY_AUTOSCALER_CREDENTIAL_KEY"]
```

Generate a Fernet key once and store it as a deployment secret:

```sh
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Run the host project's migrations after installing the package:

```sh
python manage.py migrate
```

Django applies the app migration as part of the host project's migration plan.

## Credential lifecycle

Use `CredentialService.create(...)` after the user submits a token. The service
stores only Fernet ciphertext. Use
`CredentialService.reveal(...)` immediately before creating a provider client;
never return the plaintext token to a view, log, task argument or database row.

The encryption key is deliberately separate from Django's database. Losing the
key makes stored credentials unrecoverable; rotating it requires decrypting with
the old key and re-encrypting with the new key while `key_version` is tracked.

The admin form accepts the token through a password widget and never renders its
value back. For Project tokens, it performs a read-only scope lookup and stores
the project identifier returned by Railway; operators do not need to copy it.
The environment is intentionally not stored on the credential: it is selected
when the operator configures the specific autoscaling target/resource. That
allows one credential to serve resources in different environments. Workspace
and Account tokens do not expose manual ID fields, but require a future project
selection flow before they can be used for a target.
