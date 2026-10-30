import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth, setPersistence, browserLocalPersistence } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);
export const analytics = getAnalytics(app);

// Configure Firebase Auth with persistence
export const auth = getAuth(app);

// Set persistence to local storage for "stay signed in" functionality
// This ensures users stay logged in across browser sessions
setPersistence(auth, browserLocalPersistence)
  .then(() => {
    console.log('Firebase auth persistence set to local storage');
  })
  .catch((error) => {
    console.error('Failed to set auth persistence:', error);
    // Fallback: try to set persistence again after a short delay
    setTimeout(() => {
      setPersistence(auth, browserLocalPersistence).catch((retryError) => {
        console.error('Retry failed to set auth persistence:', retryError);
      });
    }, 1000);
  }); 