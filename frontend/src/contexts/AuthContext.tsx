import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  GoogleAuthProvider,
  signInWithPopup,
} from 'firebase/auth';
import type { User } from 'firebase/auth';
import { auth } from '../config/firebase';
import { clearTokenCache } from '../utils/api';

interface AuthContextType {
  currentUser: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    console.log('AuthContext: Starting authentication check...');
    console.log('AuthContext: Auth instance:', auth);
    
    // Set a longer timeout for auth restoration
    const authTimeout = setTimeout(() => {
      console.warn('AuthContext: Authentication check timed out after 15 seconds');
      setLoading(false);
      // If we're still loading after timeout, assume no user is authenticated
      if (!currentUser) {
        console.log('AuthContext: Timeout reached, no user authenticated');
      }
    }, 15000); // Increased to 15 seconds for proper auth restoration
    
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      console.log('AuthContext: User state changed:', user ? 'Authenticated' : 'Not authenticated');
      if (user) {
        console.log('AuthContext: User details:', {
          uid: user.uid,
          email: user.email,
          emailVerified: user.emailVerified
        });
      }
      clearTimeout(authTimeout); // Clear timeout when auth state changes
      setCurrentUser(user);
      setLoading(false);
    }, (error) => {
      console.error('AuthContext: Auth state change error:', error);
      clearTimeout(authTimeout);
      setCurrentUser(null);
      setLoading(false);
    });

    return () => {
      clearTimeout(authTimeout);
      unsubscribe();
    };
  }, []); // Remove currentUser from dependency array to prevent infinite loops

  const signIn = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };

  const signUp = async (email: string, password: string) => {
    await createUserWithEmailAndPassword(auth, email, password);
  };

  const signInWithGoogle = async () => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  };

  const logout = async () => {
    await signOut(auth);
    clearTokenCache(); // Clear cached tokens on logout
  };

  const value = {
    currentUser,
    loading,
    signIn,
    signUp,
    signInWithGoogle,
    logout
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}; 