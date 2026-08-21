declare module "next/font/google" {
  import { ReactNode } from "react";

  interface FontOptions {
    subsets?: string[];
    weight?: string | string[];
    style?: string | string[];
    axes?: string | string[];
    display?: "auto" | "block" | "swap" | "fallback" | "optional";
    preload?: boolean;
    fallback?: string | string[];
    adjustFontFallback?: boolean;
    variable?: string;
    fallbackFonts?: string[];
  }

  interface FontReturn {
    className: string;
    style: {
      fontFamily: string;
    };
    variable: string;
    fontFaces: Array<{
      name: string;
      style: string;
      weight: string;
      src: string;
    }>;
  }

  export function IBM_Plex_Mono(options?: FontOptions): FontReturn;
  export function DotGothic16(options?: FontOptions): FontReturn;
  export function Inter(options?: FontOptions): FontReturn;
  export function Roboto(options?: FontOptions): FontReturn;
  export function Open_Sans(options?: FontOptions): FontReturn;
  export function Lato(options?: FontOptions): FontReturn;
  export function Montserrat(options?: FontOptions): FontReturn;
  export function Oswald(options?: FontOptions): FontReturn;
  export function Source_Code_Pro(options?: FontOptions): FontReturn;
  export function Fira_Code(options?: FontOptions): FontReturn;
  export function JetBrains_Mono(options?: FontOptions): FontReturn;
}
