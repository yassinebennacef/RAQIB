import { Link } from "react-router-dom";
import { Button, Card } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <Card className="mx-auto mt-16 max-w-md p-8 text-center">
      <h1 className="text-lg font-semibold text-slate-100">Page not found</h1>
      <p className="mt-1 text-sm text-slate-400">This page does not exist in the RAQIB control room.</p>
      <Link to="/">
        <Button className="mt-4">Back to the control room</Button>
      </Link>
    </Card>
  );
}
