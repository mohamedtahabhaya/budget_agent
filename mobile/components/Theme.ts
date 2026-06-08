import { StyleSheet } from 'react-native';

export const THEMES = {
  dark: {
    background: '#0a0a0f',
    card: '#161622',
    cardSecondary: '#1f1f30',
    border: '#2c2c3e',
    text: '#ffffff',
    textMuted: '#9aa0b9',
    primary: '#8b5cf6', // Violet
    primaryDark: '#6d28d9',
    accent: '#a78bfa',
    success: '#10b981',
    danger: '#ef4444',
    warning: '#f59e0b',
  },
  light: {
    background: '#f8fafc', // Slate 50
    card: '#ffffff',
    cardSecondary: '#f1f5f9', // Slate 100
    border: '#cbd5e1', // Slate 300
    text: '#0f172a', // Slate 900
    textMuted: '#64748b', // Slate 500
    primary: '#6366f1', // Indigo 500
    primaryDark: '#4f46e5',
    accent: '#818cf8',
    success: '#10b981',
    danger: '#ef4444',
    warning: '#f59e0b',
  }
};

export type ThemeType = 'dark' | 'light';

// Default static exports for backward compatibility (will resolve to dark theme by default)
export const COLORS = THEMES.dark;

export const getCommonStyles = (colors: typeof THEMES.dark) => {
  return StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
    card: {
      backgroundColor: colors.card,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: colors.border,
      padding: 16,
      marginBottom: 16,
    },
    title: {
      color: colors.text,
      fontSize: 18,
      fontWeight: 'bold',
      marginBottom: 12,
    },
    subtitle: {
      color: colors.textMuted,
      fontSize: 14,
      marginBottom: 8,
    },
    input: {
      backgroundColor: colors.cardSecondary,
      borderColor: colors.border,
      borderWidth: 1,
      borderRadius: 8,
      color: colors.text,
      padding: 10,
      fontSize: 14,
      marginBottom: 12,
    },
    button: {
      backgroundColor: colors.primary,
      borderRadius: 8,
      paddingVertical: 12,
      paddingHorizontal: 16,
      alignItems: 'center',
      justifyContent: 'center',
    },
    buttonText: {
      color: '#ffffff',
      fontSize: 14,
      fontWeight: 'bold',
    },
  });
};

export const COMMON_STYLES = getCommonStyles(THEMES.dark);
