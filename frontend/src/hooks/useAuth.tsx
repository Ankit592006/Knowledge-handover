import React, { createContext, useContext, useState } from "react";
import { apiClient, clearAuthTokens, setAuthTokens } from "../lib/apiClient";
import { ProjectRole, UserProfile } from "../lib/types";

interface AuthContextValue {
  user: UserProfile | null;
  activeRoleOverride: ProjectRole | null;
  setActiveRoleOverride: (role: ProjectRole | null) => void;
  effectiveRole: ProjectRole;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeRoleOverride, setActiveRoleOverride] = useState<ProjectRole | null>(null);

  const login = async (email: string, password: string) => {
    const resp = await apiClient.post("/api/v1/auth/login", { email, password });
    const { access_token, refresh_token, user: userData } = resp.data;
    setAuthTokens(access_token, refresh_token);
    setUser(userData);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const resp = await apiClient.post("/api/v1/auth/register", {
      email,
      password,
      full_name: fullName,
      platform_role: "STANDARD",
    });
    const { access_token, refresh_token, user: userData } = resp.data;
    setAuthTokens(access_token, refresh_token);
    setUser(userData);
  };

  const logout = () => {
    clearAuthTokens();
    setUser(null);
    setActiveRoleOverride(null);
  };

  const primaryProjectRole: ProjectRole =
    user?.memberships?.[0]?.project_role || "PROJECT_LEAD";

  const effectiveRole: ProjectRole = activeRoleOverride || primaryProjectRole;

  return (
    <AuthContext.Provider
      value={{
        user,
        activeRoleOverride,
        setActiveRoleOverride,
        effectiveRole,
        isAuthenticated: Boolean(user),
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
