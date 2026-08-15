"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { knowledgeApi } from "@/lib/client";
import { formatCourse } from "@/lib/utils";

export default function CoursesPage() {
  const { data, isLoading } = useQuery({ queryKey: ["knowledge-tree"], queryFn: knowledgeApi.tree });

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-5 p-6">
        <h1 className="text-xl font-semibold">Courses</h1>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data?.courses.map((course) => {
            const resources = course.modules.reduce((n, m) => n + m.resources.length, 0);
            return (
              <Link key={course.course} href="/knowledge">
                <Card className="h-full transition-shadow hover:shadow-card">
                  <CardContent className="pt-5">
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                      <BookOpen className="h-5 w-5 text-primary" />
                    </div>
                    <p className="font-medium">{formatCourse(course.course)}</p>
                    <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{course.modules.length} modules</span>
                      <span className="flex items-center gap-1"><FileText className="h-3 w-3" /> {resources} resources</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
        {data && !data.courses.length && (
          <p className="text-sm text-muted-foreground">No courses yet. Upload material in the Knowledge Base.</p>
        )}
      </div>
    </div>
  );
}
