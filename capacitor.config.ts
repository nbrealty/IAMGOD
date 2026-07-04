import type { CapacitorConfig } from "@capacitor/cli";

// Capacitor wraps the built web app (dist/) into a native iOS app for the App
// Store. To create the native project (run on a Mac with Xcode):
//   npm run build
//   npx cap add ios
//   npm run cap:ios      # syncs dist/ into the iOS project and opens Xcode
//
// The /ios directory it generates is gitignored — regenerate it rather than
// committing it. See docs/TESTING.md for the full flow.
const config: CapacitorConfig = {
  appId: "com.iamgod.app",
  appName: "I AM GOD",
  webDir: "dist",
  ios: {
    contentInset: "always",
  },
};

export default config;
