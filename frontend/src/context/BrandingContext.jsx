import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const BrandingContext = createContext(null);
const DEFAULT = { company_name: "PT Harmoni Wisata Internusa", logo: "" };

export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/public/branding");
      const b = { company_name: data.company_name || DEFAULT.company_name, logo: data.logo || "" };
      setBranding(b);
      document.title = b.company_name;
    } catch {
      document.title = DEFAULT.company_name;
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <BrandingContext.Provider value={{ ...branding, refreshBranding: load }}>
      {children}
    </BrandingContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
