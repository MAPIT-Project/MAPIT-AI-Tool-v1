import { useTheme } from '../contexts/ThemeContext';

export const useThemeColors = () => {
  const { theme } = useTheme();

  const colors = {
    light: {
      bg: '#f8fafc',
      text: '#1a202c',
      primary: '#3b82f6',
      primaryHover: '#2563eb',
      secondary: '#06b6d4',
      accent: '#06b6d4',
      surface: '#ffffff',
      border: '#e2e8f0',
      cardBg: '#ffffff',
      cardBorder: '#e2e8f0',
      sidebarBg: '#ffffff',
      sidebarBorder: '#e2e8f0',
      inputBg: '#ffffff',
      inputBorder: '#cbd5e1',
      hoverBg: '#f1f5f9',
      activeBg: '#dbeafe',
      error: '#ef4444',
      shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      gradient: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
      gradientLight: 'linear-gradient(135deg, #dbeafe 0%, #cffafe 100%)',
      gradientDark: 'linear-gradient(135deg, #2563eb 0%, #0891b2 100%)',
    },
    dark: {
      bg: '#0a0e1a',
      text: '#e2e8f0',
      primary: '#60a5fa',
      primaryHover: '#3b82f6',
      secondary: '#22d3ee',
      accent: '#22d3ee',
      surface: '#1e293b',
      border: '#334155',
      cardBg: '#1e293b',
      cardBorder: '#334155',
      sidebarBg: '#1e293b',
      sidebarBorder: '#334155',
      inputBg: '#334155',
      inputBorder: '#475569',
      hoverBg: '#334155',
      activeBg: '#1e40af',
      error: '#f87171',
      shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
      shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2)',
      gradient: 'linear-gradient(135deg, #2563eb 0%, #0891b2 100%)',
      gradientLight: 'linear-gradient(135deg, #1e3a8a 0%, #164e63 100%)',
      gradientDark: 'linear-gradient(135deg, #1d4ed8 0%, #0e7490 100%)',
    },
  };

  return colors[theme];
};
