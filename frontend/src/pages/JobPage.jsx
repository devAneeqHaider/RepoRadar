import { useParams } from "react-router-dom";
import JobProgress from "../components/JobProgress.jsx";

export default function JobPage() {
  const { jobId } = useParams();
  return <JobProgress jobId={jobId} />;
}
