# Things to note:
## Why are we running these locally
While we would have much preferred to deploy the API and both UIs, we have had a lot of trouble accessing the AWS accounts that were allocated to us. The password that I, the team leader, had set, just stopped working. 

I tried all possible ways to reset the password, but they didn't work. We emailed the main point of contact for the hackathon, who told us to wait as their tech team works on a solution. That was on the 2nd of August, and we didn't get any response till now despite further prompts

## Note on testing multiple UIs at once
As of now, our 2 UIs are not made to be run simultaneously. To avoid any unexpected outcomes, please test out each UI one at a time, and make sure to shut down the UI once done testing to ensure the locally hosted processes don't persist past testing.


# How to test main dashboard UI

`python ui/streamlit/run_dev.py` starts two local processes side by side: the FastAPI backend (`uvicorn api.main:app` on port 8000) and the Streamlit app (port 8501), which talks to the backend over HTTP.

1. Make sure `.env` at the repo root has `OPENAI_API_KEY` set (plus any other model keys the crews you're testing need).
2. From the repo root, run:
   ```
   python ui/streamlit/run_dev.py
   ```
3. Wait for both processes to log ready (API first, then Streamlit), then open **http://localhost:8501** in your browser.
4. Type a message in the chat box, e.g. "How many employees are on the roster?" or "What's our budget for this expense?", and confirm a response comes back.
5. Check the sidebar: it shows the current session ID, and after a response, an expander listing which specialist(s) were invoked.
6. **Shutdown**:
   - From the browser, open **Danger zone** in the sidebar and click **Stop servers**

# How to test tele bot UI

`python ui/telegram/run_dev.py` starts the same two local processes side by side: the FastAPI backend (port 8000) and the Telegram bot, which long-polls Telegram's servers and talks to the backend over HTTP.

1. Make sure `.env` at the repo root has `TELEGRAM_BOT_TOKEN` (from @BotFather) and `OPENAI_API_KEY` set.
2. From the repo root, run:
   ```
   python ui/telegram/run_dev.py
   ```
3. Wait for both processes to log ready (API first, then the bot).
4. On your phone or desktop, open Telegram and message your bot (`@BizRezO_bot`) — no need to be on the same network as your laptop, since the bot polls out to Telegram rather than accepting inbound connections.
5. Send `/start` and confirm you get the welcome message.
6. Send a real question, e.g. "How many employees are on the roster?", and confirm a response comes back (you'll see a "typing..." indicator while the orchestrator is working).
7. **Shutdown**, either way:
   - From Telegram, send `/shutdown` — kills the API and the bot process directly
