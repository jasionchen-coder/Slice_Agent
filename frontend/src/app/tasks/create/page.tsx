import { TaskCreateForm } from "@/components/tasks/task-create-form";

export default function CreateTaskPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">新建切片任务</h1>
        <p className="text-sm text-muted-foreground">选择直播回放并设置切片生成约束。</p>
      </div>
      <TaskCreateForm />
    </div>
  );
}
