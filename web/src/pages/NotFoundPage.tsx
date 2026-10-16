import { Link } from "react-router-dom";
import { Shell } from "../components/Shell";

export function NotFoundPage() {
  return (
    <Shell title="העמוד לא נמצא">
      <p className="empty"><strong>העמוד לא נמצא</strong><Link to="/">חזרה לעדכונים</Link></p>
    </Shell>
  );
}
