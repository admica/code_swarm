#!/bin/bash

# Exit on any error
set -e

echo "Creating frontend directory..."
# Create Next.js app with TypeScript, Tailwind, and ESLint
npx create-next-app@latest frontend \
    --typescript \
    --tailwind \
    --eslint \
    --app \
    --src-dir \
    --import-alias "@/*"

# Move into frontend directory
cd frontend

echo "Installing dependencies..."
# Install SWR and Axios for data fetching
npm install swr axios

# Install shadcn/ui dependencies
npm install @shadcn/ui
npm install @radix-ui/react-slot
npm install @radix-ui/react-scroll-area 
npm install @radix-ui/react-tabs
npm install @radix-ui/react-alert-dialog
npm install class-variance-authority
npm install clsx
npm install lucide-react
npm install tailwind-merge

# Create required directories
echo "Creating project structure..."
mkdir -p src/types
mkdir -p src/components

# Copy configuration files and base CSS
echo "Setting up shadcn/ui configuration..."
cat > components.json << EOL
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
EOL

# Create utils directory and add utilities
mkdir -p src/lib
cat > src/lib/utils.ts << EOL
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
EOL

# Update tailwind.config.js
cat > tailwind.config.js << EOL
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
	],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
EOL

# Install additional dependencies needed by tailwind config
npm install tailwindcss-animate

echo "Setup complete! Your frontend directory is ready."
echo "You can now create your components in src/components/"
echo "and add your types in src/types/"
