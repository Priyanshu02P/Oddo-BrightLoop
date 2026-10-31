# Gmail SMTP on Vercel (BrightLoop)

BrightLoop uses Django's standard SMTP backend for password-reset and quotation emails. The existing password-reset flow and `apps/subscriptions/notifications.py` quotation sender both use the same `EMAIL_*` settings. No additional Python package is needed.

## 1. Create a Gmail sending account

1. Use a dedicated Gmail account for BrightLoop (for example, `brightloop.notifications@gmail.com`).
2. Enable 2-Step Verification on that Google account.
3. Create an **App Password** at <https://myaccount.google.com/apppasswords>. If Google does not offer App Passwords, check the account's security eligibility and 2-Step Verification settings.
4. Copy the generated 16-character app password. It is not your normal Gmail password. Remove any spaces when placing it in the environment variable.

Use the same Gmail address for `EMAIL_HOST_USER` and `DEFAULT_FROM_EMAIL`. Gmail may reject or rewrite a sender address that does not belong to the authenticated account.

## 2. Set Vercel environment variables

In **Vercel Dashboard → BrightLoop project → Settings → Environment Variables**, add the following variables. Apply them to **Production** (and Preview too, if you want email to work in preview deployments). Then redeploy.

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=brightloop.notifications@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-google-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=15
DEFAULT_FROM_EMAIL=BrightLoop <brightloop.notifications@gmail.com>
```

Replace both example email addresses with the actual Gmail account you created. Put the App Password in Vercel only; never commit it to Git, `.env.example`, source code, or chat. Do not add quotation marks around the values in Vercel. Do not set `EMAIL_USE_TLS` and `EMAIL_USE_SSL` to `True` at the same time. Port 587 uses STARTTLS.

## 3. Keep local development on Mailpit

The checked-in `.env.example` defaults to Mailpit for local development. Start it with:

```bash
docker compose up -d mailpit
```

Mailpit captures messages locally and does not deliver them to real recipients. For local real-email testing, temporarily put the Gmail values in your untracked `.env` file. Never commit `.env`.

## 4. Send a test email

After deploying, run a test through a temporary protected management command or a one-off authenticated admin action. For local testing with Gmail configured in `.env`, this command sends to an address you control:

```bash
python manage.py shell -c "from django.core.mail import send_mail; from django.conf import settings; print(send_mail('BrightLoop SMTP test', 'Gmail SMTP is configured.', settings.DEFAULT_FROM_EMAIL, ['YOUR_TEST_ADDRESS@gmail.com'], fail_silently=False))"
```

A return value of `1` means Django handed the message to Gmail's SMTP server; it does not guarantee inbox placement. Then test the actual password-reset flow and quotation notification flow.

## Notes and limitations

- Gmail SMTP can send to users at Gmail, Outlook, Yahoo, and other email providers; recipients do not need a Gmail account.
- Personal Gmail accounts have sending limits and are intended for low-volume transactional use, not bulk marketing. Google may temporarily block sending if its limits or abuse controls are triggered.
- The Vercel deployment must have the SMTP environment variables configured. If they are missing, the existing local Mailpit defaults (`localhost:1025`) will not work in production.
- SMTP delivery happens during the Django request in the current implementation. Keep email volume modest; for high volume, move to a transactional email provider and/or a durable background queue.
