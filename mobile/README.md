# Budget Agent Mobile Client - React Native (Expo)

Cette application mobile est le client natif de l'Assistant Financier Multi-comptes (**Budget Agent**), conforme à 100% à la spécification produit. Elle est conçue sous forme de tableau de bord moderne sombre (dark mode) intégrant une interface de chat asynchrone avec l'intelligence artificielle, des fonctionnalités d'enregistrement de notes vocales (micro natif) et d'analyse visuelle de tickets de caisse (caméra native).

---

## 📱 Structure de l'Application

L'interface mobile est découpée en 3 onglets principaux (bottom tab navigation) :
1. **Dashboard (📊)** : Affiche en temps réel le solde consolidé (MAD/devises), les cartes des différents comptes bancaires, les jauges de progression des objectifs d'épargne, les alertes de budgets critiques et le journal des transactions récentes.
2. **Assistant Chat (💬)** : Une interface de discussion fluide et progressive (streaming token par token) avec l'agent IA, prenant en charge le texte, les photos de tickets de caisse (vision) et l'enregistrement de notes vocales (whisper).
3. **Settings (⚙️)** : Permet d'administrer l'espace de travail (nom, devise de référence, modèle de répartition avec grille de splits sur-mesure), d'ajuster les plafonds de budgets mensuels par catégorie, de gérer le cycle de vie des comptes (création, archivage) et de piloter les canaux de notifications de l'utilisateur.

---

## 🚀 Lancement du Client Mobile

Pour démarrer et tester l'application mobile locale :

### 1. Prérequis
Assurez-vous que votre serveur backend FastAPI est démarré et écoute sur le port `8000`.

### 2. Démarrage du serveur de développement Expo
Ouvrez votre terminal et naviguez dans le sous-dossier `mobile` :
```bash
cd mobile
npm start
```
Cela va lancer le serveur de développement Expo et afficher un **QR Code** dans votre terminal.

---

## 🧪 Tester sur votre Téléphone (Recommandé)

Grâce à **Expo Go**, vous n'avez pas besoin d'installer Xcode ou Android Studio pour voir l'application tourner sur un appareil physique :

1. Téléchargez l'application gratuite **Expo Go** sur votre smartphone :
   * [App Store (iOS)](https://apps.apple.com/fr/app/expo-go/id984021056)
   * [Google Play Store (Android)](https://play.google.com/store/apps/details?id=host.exp.exponent)
2. Connectez votre ordinateur et votre téléphone sur le **même réseau Wi-Fi**.
3. **Ajustez l'adresse API** : 
   Ouvrez le fichier [mobile/config.ts](file:///Users/mohamed-taha/Documents/budget_agent/mobile/config.ts) et remplacez `http://localhost:8000` par l'adresse IP locale de votre ordinateur (ex: `http://192.168.1.50:8000`) afin que votre smartphone puisse joindre l'API de votre ordinateur sur le réseau Wi-Fi.
4. Scannez le QR Code affiché dans votre terminal avec l'appareil photo de votre smartphone (ou l'application Expo Go sur Android).
5. L'application mobile se charge et s'affiche instantanément sur votre téléphone !

---

## 🖥️ Tester sur un Émulateur (iOS / Android)

Si vous avez installé Xcode (sur macOS) ou Android Studio :

* **Pour iOS (Simulateur Mac)** :
  Appuyez sur `i` dans le terminal après avoir lancé `npm start`.
* **Pour Android (Émulateur)** :
  Appuyez sur `a` dans le terminal. (L'application est configurée pour mapper automatiquement localhost vers `http://10.0.2.2:8000` pour Android).
