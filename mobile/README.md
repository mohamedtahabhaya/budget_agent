# Budget Agent Mobile Client

A React Native mobile client built with **Expo** and styled in dark mode. It interfaces with the FastAPI backend to display balances, transactions, and settings, and provides an AI Chat dashboard that supports text, voice recordings, and receipt uploads.

---

## 📱 Project Structure

The client includes 3 primary tabs:
1. **Dashboard**: Live consolidation cards (MAD/currencies), budget limits tracking, savings goal progress, recent transaction history, and real-time SSE budget notifications.
2. **Chat**: Interface with the LangGraph financial advisor. Supports token streaming, receipt analysis (Vision), and voice notes (Whisper).
3. **Settings**: Configuration panels for the workspace (naming, reference currency, equal/proportional/custom split rules), category monthly budget limits, account management (creation, rename, archive), and notification toggles.

---

## 🚀 Setup & Launch

### 1. Install Dependencies
Navigate to the `mobile` directory and install the packages:
```bash
cd mobile
npm install
```

### 2. Configure Backend API Endpoint
Open [mobile/config.ts](file:///Users/mohamed-taha/Documents/budget_agent/mobile/config.ts) and set the `API_BASE_URL` to match your environment:
- **Web Browser testing**: Use `http://localhost:8000`.
- **Physical Device (Expo Go)**: Use your computer's local IP address (e.g., `http://192.168.1.50:8000`).

---

## 🧪 Running the App

### Web Mode (Recommended for quick testing)
Start the app in your browser:
```bash
npm run web
```
*Note: Web browser uploads for receipt image capture are supported. Standard browser APIs are used to read file blobs, bypassing mobile-only `expo-file-system` limitations.*

### Mobile Device Mode (iOS / Android)
Start the Expo packager:
```bash
npm start
```
1. Install **Expo Go** on your device.
2. Ensure your phone and computer are on the **same Wi-Fi network**.
3. Scan the QR code displayed in the terminal to load the application.
