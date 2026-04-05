/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // I'M brand
        brand: {
          yellow: "#FDB714",
          red:    "#E52823",
          dark:   "#231F20",
          muted:  "#6D6258",
          bg:     "#F5F1EB",
          border: "#E3D8CA",
        },
        sidebar: "#1B1B1B",
      },
      fontFamily: {
        sans: ["Inter", "Arial", "sans-serif"],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
    },
  },
  plugins: [],
}
