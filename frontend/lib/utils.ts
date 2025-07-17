import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Removes the .iic extension from a filename.
 * @param filename The original filename.
 * @returns The filename without the .iic extension.
 */
export function removeIicExtension(filename: string): string {
  if (filename.endsWith('.iic')) {
    return filename.slice(0, -4); // Remove the trailing '.iic'
  }
  return filename;
}
