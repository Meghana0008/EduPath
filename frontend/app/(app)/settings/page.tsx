"use client";

import { useAuth } from "@/lib/auth-context";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Account preferences and environment information."
      />

      <div className="grid lg:grid-cols-2 gap-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <span className="text-xs text-ocean-500">Name</span>
              <p className="font-medium text-ocean-900">{user?.name}</p>
            </div>
            <div>
              <span className="text-xs text-ocean-500">Email</span>
              <p className="font-medium text-ocean-900">{user?.email}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-ocean-500">Account Type</span>
              <Badge variant="ocean">Student</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Discovery focus</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <span className="text-xs text-ocean-500">Region</span>
              <p className="font-medium text-ocean-900">India</p>
            </div>
            <div>
              <span className="text-xs text-ocean-500">API URL</span>
              <p className="font-mono text-sm text-ocean-800">
                {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-ocean-500">Mode</span>
              <Badge variant="success">Production</Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Session</CardTitle>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
