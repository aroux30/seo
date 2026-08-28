"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  is_active: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  description?: string;
  my_role?: string;
}

export interface Website {
  id: string;
  project_id: string;
  organization_id: string;
  name: string;
  domain: string;
  base_url: string;
  website_type: string;
  language: string;
  country?: string;
  automation_mode: string;
  status: string;
}

interface AuthContextType {
  user: UserProfile | null;
  organizations: Organization[];
  currentOrg: Organization | null;
  setCurrentOrg: (org: Organization | null) => void;
  websites: Website[];
  currentWebsite: Website | null;
  setCurrentWebsite: (site: Website | null) => void;
  loading: boolean;
  login: (accessToken: string, refreshToken: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshOrgsAndWebsites: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrg, setCurrentOrgState] = useState<Organization | null>(null);
  const [websites, setWebsites] = useState<Website[]>([]);
  const [currentWebsite, setCurrentWebsiteState] = useState<Website | null>(null);
  const [loading, setLoading] = useState(true);

  const setCurrentOrg = async (org: Organization | null) => {
    setCurrentOrgState(org);
    if (org) {
      localStorage.setItem("current_org_id", org.id);
      try {
        const sites = await api.get<Website[]>("/websites");
        setWebsites(sites);
        let selectedSite = null;
        const savedSiteId = localStorage.getItem("current_website_id");
        if (savedSiteId) {
          selectedSite = sites.find((s) => s.id === savedSiteId) || null;
        }
        if (!selectedSite && sites.length > 0) {
          selectedSite = sites[0];
        }
        setCurrentWebsiteState(selectedSite);
        if (selectedSite) {
            localStorage.setItem("current_website_id", selectedSite.id);
        } else {
            localStorage.removeItem("current_website_id");
        }
      } catch (err) {
        setWebsites([]);
        setCurrentWebsiteState(null);
        localStorage.removeItem("current_website_id");
      }
    } else {
      localStorage.removeItem("current_org_id");
      setWebsites([]);
      setCurrentWebsiteState(null);
      localStorage.removeItem("current_website_id");
    }
  };

  const setCurrentWebsite = (site: Website | null) => {
    setCurrentWebsiteState(site);
    if (site) {
      localStorage.setItem("current_website_id", site.id);
    } else {
      localStorage.removeItem("current_website_id");
    }
  };

  const loadProfile = async () => {
    try {
      const u = await api.get<UserProfile>("/auth/me");
      setUser(u);
      await refreshOrgsAndWebsites();
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const refreshOrgsAndWebsites = async () => {
    try {
      const orgs = await api.get<Organization[]>("/organizations");
      setOrganizations(orgs);

      let selectedOrg = null;
      const savedOrgId = localStorage.getItem("current_org_id");
      if (savedOrgId) {
        selectedOrg = orgs.find((o) => o.id === savedOrgId) || null;
      }
      if (!selectedOrg && orgs.length > 0) {
        selectedOrg = orgs[0];
      }
      setCurrentOrgState(selectedOrg); // Use raw state setter to avoid unnecessary fetch during initial load
      if (selectedOrg) {
        localStorage.setItem("current_org_id", selectedOrg.id);
      } else {
        localStorage.removeItem("current_org_id");
      }

      if (selectedOrg) {
        const sites = await api.get<Website[]>("/websites");
        setWebsites(sites);
        let selectedSite = null;
        const savedSiteId = localStorage.getItem("current_website_id");
        if (savedSiteId) {
          selectedSite = sites.find((s) => s.id === savedSiteId) || null;
        }
        if (!selectedSite && sites.length > 0) {
          selectedSite = sites[0];
        }
        setCurrentWebsite(selectedSite);
      } else {
        setWebsites([]);
        setCurrentWebsite(null);
      }
    } catch {
      setOrganizations([]);
      setWebsites([]);
    }
  };

  const login = async (accessToken: string, refreshToken: string) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    await loadProfile();
  };

  const logout = async () => {
    try {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        await api.post("/auth/logout", { refresh_token: refreshToken });
      }
    } catch {
      // ignore
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("current_org_id");
      localStorage.removeItem("current_website_id");
      setUser(null);
      setOrganizations([]);
      setCurrentOrgState(null);
      setWebsites([]);
      setCurrentWebsiteState(null);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      loadProfile();
    } else {
      setLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        organizations,
        currentOrg,
        setCurrentOrg,
        websites,
        currentWebsite,
        setCurrentWebsite,
        loading,
        login,
        logout,
        refreshOrgsAndWebsites,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
