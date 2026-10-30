import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

const theme = extendTheme({
  config,
  breakpoints: {
    base: '0em',    // 0px
    sm: '30em',     // 480px
    md: '48em',     // 768px
    lg: '62em',     // 992px
    xl: '80em',     // 1280px
    '2xl': '96em',  // 1536px
  },
  styles: {
    global: (props: any) => ({
      body: {
        bg: props.colorMode === 'dark' ? '#0a0e1a' : '#f8fafc',
        color: props.colorMode === 'dark' ? '#e2e8f0' : '#1a202c',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        // Mobile-specific body styles
        fontSize: { base: '14px', md: '16px' },
        lineHeight: { base: '1.4', md: '1.5' },
      },
      // Mobile touch improvements
      '*': {
        WebkitTapHighlightColor: 'transparent',
      },
      // Better mobile scrolling
      'html, body': {
        WebkitOverflowScrolling: 'touch',
        scrollBehavior: 'smooth',
      },
    }),
  },
  colors: {
    // AI/Technology theme colors
    ai: {
      // Primary blues
      primary: {
        50: '#eff6ff',
        100: '#dbeafe',
        200: '#bfdbfe',
        300: '#93c5fd',
        400: '#60a5fa',
        500: '#3b82f6',
        600: '#2563eb',
        700: '#1d4ed8',
        800: '#1e40af',
        900: '#1e3a8a',
      },
      // Accent cyans
      accent: {
        50: '#ecfeff',
        100: '#cffafe',
        200: '#a5f3fc',
        300: '#67e8f9',
        400: '#22d3ee',
        500: '#06b6d4',
        600: '#0891b2',
        700: '#0e7490',
        800: '#155e75',
        900: '#164e63',
      },
      // Neutral grays
      neutral: {
        50: '#f8fafc',
        100: '#f1f5f9',
        200: '#e2e8f0',
        300: '#cbd5e1',
        400: '#94a3b8',
        500: '#64748b',
        600: '#475569',
        700: '#334155',
        800: '#1e293b',
        900: '#0f172a',
      },
      // Success greens
      success: {
        50: '#f0fdf4',
        100: '#dcfce7',
        200: '#bbf7d0',
        300: '#86efac',
        400: '#4ade80',
        500: '#22c55e',
        600: '#16a34a',
        700: '#15803d',
        800: '#166534',
        900: '#14532d',
      },
      // Warning oranges
      warning: {
        50: '#fffbeb',
        100: '#fef3c7',
        200: '#fde68a',
        300: '#fcd34d',
        400: '#fbbf24',
        500: '#f59e0b',
        600: '#d97706',
        700: '#b45309',
        800: '#92400e',
        900: '#78350f',
      },
      // Error reds
      error: {
        50: '#fef2f2',
        100: '#fee2e2',
        200: '#fecaca',
        300: '#fca5a5',
        400: '#f87171',
        500: '#ef4444',
        600: '#dc2626',
        700: '#b91c1c',
        800: '#991b1b',
        900: '#7f1d1d',
      },
    },
    // Light theme colors
    light: {
      bg: '#f8fafc',
      text: '#1a202c',
      primary: '#3b82f6',
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
      shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    },
    // Dark theme colors
    dark: {
      bg: '#0a0e1a',
      text: '#e2e8f0',
      primary: '#60a5fa',
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
      shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
      shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2)',
    },
  },
  components: {
    Button: {
      variants: {
        solid: (props: any) => ({
          bg: props.colorMode === 'dark' ? 'ai.primary.600' : 'ai.primary.500',
          color: 'white',
          fontWeight: '600',
          borderRadius: 'lg',
          _hover: {
            bg: props.colorMode === 'dark' ? 'ai.primary.500' : 'ai.primary.600',
            transform: 'translateY(-1px)',
            boxShadow: props.colorMode === 'dark' ? '0 10px 15px -3px rgba(96, 165, 250, 0.3)' : '0 10px 15px -3px rgba(59, 130, 246, 0.3)',
          },
          _active: {
            bg: props.colorMode === 'dark' ? 'ai.primary.700' : 'ai.primary.700',
            transform: 'translateY(0)',
          },
          transition: 'all 0.2s ease-in-out',
          // Mobile-specific button improvements
          minH: { base: '44px', md: 'auto' },
          minW: { base: '44px', md: 'auto' },
        }),
        ghost: (props: any) => ({
          color: props.colorMode === 'dark' ? 'ai.neutral.200' : 'ai.neutral.700',
          _hover: {
            bg: props.colorMode === 'dark' ? 'ai.neutral.700' : 'ai.neutral.100',
          },
          _active: {
            bg: props.colorMode === 'dark' ? 'ai.neutral.600' : 'ai.neutral.200',
          },
          transition: 'all 0.2s ease-in-out',
          // Mobile-specific button improvements
          minH: { base: '44px', md: 'auto' },
          minW: { base: '44px', md: 'auto' },
        }),
        outline: (props: any) => ({
          borderColor: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.500',
          color: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.500',
          _hover: {
            bg: props.colorMode === 'dark' ? 'ai.primary.900' : 'ai.primary.50',
          },
          transition: 'all 0.2s ease-in-out',
          // Mobile-specific button improvements
          minH: { base: '44px', md: 'auto' },
          minW: { base: '44px', md: 'auto' },
        }),
      },
    },
    Input: {
      variants: {
        filled: (props: any) => ({
          field: {
            bg: props.colorMode === 'dark' ? 'ai.neutral.700' : 'ai.neutral.50',
            border: '1px solid',
            borderColor: props.colorMode === 'dark' ? 'ai.neutral.600' : 'ai.neutral.200',
            borderRadius: 'lg',
            _hover: {
              borderColor: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.300',
            },
            _focus: {
              borderColor: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.500',
              boxShadow: props.colorMode === 'dark' ? '0 0 0 1px rgba(96, 165, 250, 0.3)' : '0 0 0 1px rgba(59, 130, 246, 0.3)',
            },
            // Mobile-specific input improvements
            fontSize: { base: '16px', md: 'inherit' },
            minH: { base: '44px', md: 'auto' },
          },
        }),
      },
      defaultProps: {
        variant: 'filled',
      },
    },
    Textarea: {
      variants: {
        filled: (props: any) => ({
          bg: props.colorMode === 'dark' ? 'ai.neutral.700' : 'ai.neutral.50',
          border: '1px solid',
          borderColor: props.colorMode === 'dark' ? 'ai.neutral.600' : 'ai.neutral.200',
          borderRadius: 'lg',
          _hover: {
            borderColor: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.300',
          },
          _focus: {
            borderColor: props.colorMode === 'dark' ? 'ai.primary.400' : 'ai.primary.500',
            boxShadow: props.colorMode === 'dark' ? '0 0 0 1px rgba(96, 165, 250, 0.3)' : '0 0 0 1px rgba(59, 130, 246, 0.3)',
          },
          // Mobile-specific textarea improvements
          fontSize: { base: '16px', md: 'inherit' },
          minH: { base: '44px', md: 'auto' },
        }),
      },
      defaultProps: {
        variant: 'filled',
      },
    },
    Box: {
      baseStyle: (props: any) => ({
        bg: props.colorMode === 'dark' ? 'ai.neutral.800' : 'white',
        color: props.colorMode === 'dark' ? 'ai.neutral.100' : 'ai.neutral.800',
      }),
    },
    Card: {
      baseStyle: (props: any) => ({
        container: {
          bg: props.colorMode === 'dark' ? 'ai.neutral.800' : 'white',
          border: '1px solid',
          borderColor: props.colorMode === 'dark' ? 'ai.neutral.700' : 'ai.neutral.200',
          borderRadius: 'xl',
          boxShadow: props.colorMode === 'dark' ? '0 4px 6px -1px rgba(0, 0, 0, 0.3)' : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        },
      }),
    },
    // Mobile-specific component improvements
    IconButton: {
      baseStyle: () => ({
        minH: { base: '44px', md: 'auto' },
        minW: { base: '44px', md: 'auto' },
        borderRadius: 'lg',
        transition: 'all 0.2s ease-in-out',
      }),
    },
    Drawer: {
      baseStyle: (props: any) => ({
        overlay: {
          bg: props.colorMode === 'dark' ? 'rgba(0, 0, 0, 0.8)' : 'rgba(0, 0, 0, 0.6)',
          backdropFilter: 'blur(4px)',
        },
        content: {
          bg: props.colorMode === 'dark' ? 'ai.neutral.800' : 'white',
          border: '1px solid',
          borderColor: props.colorMode === 'dark' ? 'ai.neutral.700' : 'ai.neutral.200',
          borderRadius: { base: '0', md: 'xl' },
          boxShadow: props.colorMode === 'dark' ? '0 20px 25px -5px rgba(0, 0, 0, 0.5)' : '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
        },
      }),
    },
  },
  fonts: {
    heading: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    body: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
  fontWeights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  radii: {
    none: '0',
    sm: '0.125rem',
    base: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    '3xl': '1.5rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    outline: '0 0 0 3px rgba(66, 153, 225, 0.6)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
    none: 'none',
  },
});

export default theme; 