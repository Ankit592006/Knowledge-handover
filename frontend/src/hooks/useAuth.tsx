import React, { createContext, useContext, useState } from "react";
import { apiClient, clearAuthTokens, setAuthTokens } from "../lib/apiClient";
import { AccessClassification, ProjectRole, UserProfile } from "../lib/types";

interface AuthContextValue {
  user: UserProfile | null;
  effectiveRole: ProjectRole;
  allowedClassifications: AccessClassification[];
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  register: (email: string, password: string, fullName: string) => Promise<UserProfile>;
  switchDemoRole: (role: ProjectRole) => Promise<UserProfile | null>;
  refreshProfile: () => Promise<UserProfile | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);

  const login = async (email: string, password: string): Promise<UserProfile> => {
    const resp = await apiClient.post("/api/v1/auth/login", { email, password });
    const { access_token, refresh_token, user: userData } = resp.data;
    setAuthTokens(access_token, refresh_token);
    setUser(userData);
    return userData;
  };

  const register = async (email: string, password: string, fullName: string): Promise<UserProfile> => {
    const resp = await apiClient.post("/api/v1/auth/register", {
      email,
      password,
      full_name: fullName,
      platform_role: "STANDARD",
    });
    const { access_token, refresh_token, user: userData } = resp.data;
    setAuthTokens(access_token, refresh_token);
    setUser(userData);
    return userData;
  };

  const switchDemoRole = async (role: ProjectRole): Promise<UserProfile | null> => {
    if (role === "GUEST_DEMO") {
      clearAuthTokens();
      setUser(null);
      return null;
    }
    const resp = await apiClient.post("/api/v1/demo/switch-role", {
      project_role: role,
    });
    const { access_token, refresh_token, user: userData } = resp.data;
    setAuthTokens(access_token, refresh_token);
    setUser(userData);
    return userData;
  };

  const refreshProfile = async (): Promise<UserProfile | null> => {
    try {
      const resp = await apiClient.get("/api/v1/auth/me");
      setUser(resp.data);
      return resp.data;
    } catch {
      return user;
    }
  };

  const logout = () => {
    clearAuthTokens();
    setUser(null);
  };

  const activeMembership =
    user?.memberships?.find((m) => m.project_slug === "payflow") ||
    user?.memberships?.[0] ||
    null;

  const effectiveRole: ProjectRole = !user
    ? "GUEST_DEMO"
    : activeMembership?.project_role || "PROJECT_LEAD";

  const allowedClassifications: AccessClassification[] = !user
    ? ["PUBLIC", "INTERNAL"]
    : activeMembership?.allowed_classifications || ["PUBLIC", "INTERNAL"];

  return (
    <AuthContext.Provider
      value={{
        user,
        effectiveRole,
        allowedClassifications,
        isAuthenticated: Boolean(user),
        login,
        register,
        switchDemoRole,
        refreshProfile,
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
