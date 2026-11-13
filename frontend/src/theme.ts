import { createTheme } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'cyan',
  primaryShade: { light: 8, dark: 6 },
  defaultRadius: 'md',
  // Noto covers Latin and Devanagari with matching metrics, so mixed
  // English/Hindi text lines up. Both fonts are bundled (works offline).
  fontFamily: "'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif",
  headings: { fontFamily: "'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif" },
  components: {
    NumberInput: { defaultProps: { hideControls: true } },
    Table: { defaultProps: { verticalSpacing: 'xs' } },
  },
});
