# FMS setup guide

For whoever installs FMS on the owner's laptop and phone. Allow about 30 minutes.

## What you need

- The owner's **Windows 10 or 11 laptop** (this becomes the "hub" that keeps all data).
- The owner's **phone** (Android or iPhone) and any other PC that should use FMS.
- Internet on each device for the first setup.
- The installer: `FMS-Setup-<version>.exe` — download it from the project's GitHub
  release (or the latest CI run's artifacts).

## 1. Install FMS on the laptop

1. Double-click `FMS-Setup-<version>.exe`.
2. Windows may show **"Windows protected your PC"** because the installer isn't signed
   with a paid certificate. Click **More info → Run anyway**.
3. Keep **"Start FMS automatically when Windows starts"** ticked, then **Install**.
4. FMS opens in its own window. **Set the owner password** (at least 6 characters) and
   give this device a name, e.g. *Owner's laptop*.
5. In **Settings**:
   - Fill in the **factory name** in English and Hindi (printed on wage slips).
   - Under **Backups**, optionally set a second folder (e.g. a USB drive or a Google
     Drive folder) so backups exist outside the laptop too.
6. Add the **rates** (Rates page) and **workers** (Workers page).

FMS now runs in the **system tray** (next to the clock). Right-click its icon for
*Open FMS*, *Open data folder* and *Quit FMS*.

**Keep the laptop from sleeping** while it's meant to be available to phones:
Settings → System → Power → *When plugged in, put my device to sleep after* → **Never**.

## 2. Connect phones and other PCs (Tailscale)

Phones reach the laptop through **Tailscale**, a free private network between your own
devices. Nothing is stored on anyone else's server.

On the **laptop**:

1. Install Tailscale from <https://tailscale.com/download> and sign in (a Google or
   Microsoft account is fine). Use **one account** for all of the owner's devices.
2. In the Tailscale admin page, under **DNS**, make sure **MagicDNS** and
   **HTTPS certificates** are enabled.
3. Open **Command Prompt** and run once:

   ```
   tailscale serve --bg 8765
   ```

   This publishes FMS privately at `https://<laptop-name>.<tailnet>.ts.net/` and keeps
   doing so after restarts.

On **each phone / PC**:

1. Install the Tailscale app and sign in with **the same account**.
2. On the laptop, open FMS → **Settings → Connect a phone**: scan the QR code with the
   phone's camera (or type the address shown).
3. Log in with the owner password, and give the device a name (*Owner's phone*).
4. Install it as an app:
   - **Android (Chrome):** menu ⋮ → **Install app** / **Add to Home screen**.
   - **iPhone (Safari):** Share → **Add to Home Screen**.

The phone app now works **even when the laptop is off**; changes are sent
automatically the next time the laptop can be reached.

FMS also has an optional **PIN lock** (Settings → Security). It's off by default and
isn't needed for normal use; each device only asks for the password once, at login.

## 3. Check it works

- On the phone, with the laptop **on**: add a production entry → header shows *All saved*.
- Switch the laptop's Wi-Fi off: add another entry → header shows *1 change waiting*.
- Switch it back on: within a few seconds the header returns to *All saved*, and the
  entry appears on the laptop.

## Updating FMS

Run the newer `FMS-Setup-<version>.exe` on the laptop. Data is kept. Phones pick up the
new version automatically next time they reach the laptop (they show *A new version is
ready → Update now*).

## If something goes wrong

| Problem | What to do |
|---|---|
| Owner forgot the password | On the laptop: Start menu → **Reset FMS password**. Every device must log in again. |
| Owner set a PIN and forgot it | On the lock screen: *Forgot PIN? Log in with the password*. |
| A phone was lost | On any logged-in device: **Settings → Security → Devices → Sign out**. |
| Phone says *Laptop not reachable* | Laptop on? Not asleep? Tailscale running on both? FMS in the tray? |
| Data looks wrong after a mistake | **Settings → Backups → Restore** an earlier backup (a copy of the current data is saved first). |
| Need help from a technician | **Settings → About** shows the version, data folder and log file. Send them `fms.log`. |

Data lives in `%LOCALAPPDATA%\FMS` on the laptop (`fms.db` = the database,
`backups\`, `logs\`). Uninstalling FMS never deletes it.
