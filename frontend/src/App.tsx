import { ChakraProvider } from '@chakra-ui/react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { LandingPage } from './components/LandingPage'
import { Chat } from './components/Chat'
import { Auth } from './components/Auth'
import { ProtectedRoute } from './components/ProtectedRoute'
import { TestRoute } from './components/TestRoute'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import theme from './config/theme'
import './App.css'

function App() {
  return (
    <ErrorBoundary>
      <ChakraProvider theme={theme}>
        <ThemeProvider>
          <AuthProvider>
            <Router>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/auth" element={<Auth />} />
                <Route path="/test" element={<TestRoute />} />
                <Route 
                  path="/chat" 
                  element={
                    <ProtectedRoute>
                      <Chat />
                    </ProtectedRoute>
                  } 
                />
                {/* Fallback route for any unmatched paths */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Router>
          </AuthProvider>
        </ThemeProvider>
      </ChakraProvider>
    </ErrorBoundary>
  )
}

export default App
