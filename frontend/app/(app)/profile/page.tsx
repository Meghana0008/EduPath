"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { PageHeader, LoadingSpinner } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getProfile().then(setProfile).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const update = (field: keyof Profile, value: unknown) => {
    if (!profile) return;
    setProfile({ ...profile, [field]: value });
  };

  const save = async () => {
    if (!profile) return;
    setSaving(true);
    setMessage("");
    try {
      const updated = await api.updateProfile({
        degree: profile.degree,
        field_of_study: profile.field_of_study,
        institution: profile.institution,
        gpa: profile.gpa,
        graduation_year: profile.graduation_year,
        country: profile.country,
        state: profile.state,
        city: profile.city,
        skills: profile.skills,
        interests: profile.interests,
        career_goals: profile.career_goals,
        education_level: profile.education_level,
        category: profile.category,
      });
      setProfile(updated);
      setMessage("Profile saved successfully");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!profile) return <p className="text-ocean-600">Profile not found.</p>;

  return (
    <>
      <PageHeader
        title="Your Profile"
        subtitle="Help EduPath AI understand your background to find the best matches."
        action={
          <Button onClick={save} loading={saving}>
            <Save className="w-4 h-4" />
            Save Profile
          </Button>
        }
      />

      {message && (
        <p className="mb-4 text-sm text-ocean-700 bg-ocean-50 rounded-lg px-4 py-2">{message}</p>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Education</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Degree</Label>
              <Input value={profile.degree || ""} onChange={(e) => update("degree", e.target.value)} placeholder="Bachelor of Science" />
            </div>
            <div>
              <Label>Field of Study</Label>
              <Input value={profile.field_of_study || ""} onChange={(e) => update("field_of_study", e.target.value)} placeholder="Computer Science" />
            </div>
            <div>
              <Label>Institution</Label>
              <Input value={profile.institution || ""} onChange={(e) => update("institution", e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>GPA</Label>
                <Input type="number" step="0.01" value={profile.gpa ?? ""} onChange={(e) => update("gpa", e.target.value ? parseFloat(e.target.value) : null)} />
              </div>
              <div>
                <Label>Graduation Year</Label>
                <Input type="number" value={profile.graduation_year ?? ""} onChange={(e) => update("graduation_year", e.target.value ? parseInt(e.target.value) : null)} />
              </div>
            </div>
            <div>
              <Label>Education Level</Label>
              <Input value={profile.education_level || ""} onChange={(e) => update("education_level", e.target.value)} placeholder="Undergraduate" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Location & Background</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Country</Label>
              <Input value={profile.country || ""} onChange={(e) => update("country", e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>State</Label>
                <Input value={profile.state || ""} onChange={(e) => update("state", e.target.value)} />
              </div>
              <div>
                <Label>City</Label>
                <Input value={profile.city || ""} onChange={(e) => update("city", e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Category</Label>
              <Input value={profile.category || ""} onChange={(e) => update("category", e.target.value)} placeholder="General / SC / ST / OBC" />
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Skills, Interests & Goals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Skills (comma-separated)</Label>
              <Textarea
                value={(profile.skills || []).join(", ")}
                onChange={(e) => update("skills", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                placeholder="Python, Machine Learning, Research"
              />
            </div>
            <div>
              <Label>Interests (comma-separated)</Label>
              <Textarea
                value={(profile.interests || []).join(", ")}
                onChange={(e) => update("interests", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
              />
            </div>
            <div>
              <Label>Career Goals (comma-separated)</Label>
              <Textarea
                value={(profile.career_goals || []).join(", ")}
                onChange={(e) => update("career_goals", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
