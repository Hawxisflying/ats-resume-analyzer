"use client";

import { useEffect, useState } from "react";
import api from "../../services/api";

interface HistoryItem {
    id: number;
    resume_name: string;
    ats_score: number;
    skills_score: number;
    experience_score: number;
    education_score: number;
    certification_score: number;
    project_score: number;
    created_at: string;
}

function tierFor(score: number) {
    if (score >= 75) {
        return { label: "Strong match", className: "text-green-600 font-bold" };
    }
    if (score >= 50) {
        return { label: "Needs improvement", className: "text-yellow-600 font-bold" };
    }
    return { label: "Weak match", className: "text-red-600 font-bold" };
}

export default function HistoryPage() {

    const [history, setHistory] = useState<HistoryItem[]>([]);

    useEffect(() => {

        loadHistory();

    }, []);

    const loadHistory = async () => {

        const res = await api.get("/api/history");

        setHistory(res.data);

    };

    const formatDate = (dateStr: string) => {

        const date = new Date(dateStr);

        const datePart = date.toLocaleDateString("en-GB", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });

        const timePart = date.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });

        return `${datePart}, ${timePart}`;

    };

    return (

        <div className="max-w-6xl mx-auto p-10">

            <h1 className="text-4xl font-bold mb-8">

                ATS Analysis History

            </h1>

            <table className="w-full border">

                <thead>

                    <tr className="bg-gray-200">

                        <th className="border p-3">Resume</th>

                        <th className="border p-3">ATS</th>

                        <th className="border p-3">Skills</th>

                        <th className="border p-3">Experience</th>

                        <th className="border p-3">Education</th>

                        <th className="border p-3">Certifications</th>

                        <th className="border p-3">Projects</th>

                        <th className="border p-3">Date</th>

                        <th className="border p-3">Status</th>

                    </tr>

                </thead>

                <tbody>

                    {history.map((item) => {

                        const tier = tierFor(item.ats_score);

                        return (

                        <tr key={item.id}>

                            <td className="border p-3">

                                {item.resume_name}

                            </td>

                            <td className="border p-3">

                                <span className={tier.className}>

                                    {item.ats_score}%

                                </span>

                            </td>

                            <td className="border p-3">

                                {item.skills_score}%

                            </td>

                            <td className="border p-3">

                                {item.experience_score}%

                            </td>

                            <td className="border p-3">

                                {item.education_score}%

                            </td>

                            <td className="border p-3">

                                {item.certification_score}%

                            </td>

                            <td className="border p-3">

                                {item.project_score}%

                            </td>

                            <td className="border p-3">
                                {formatDate(item.created_at)}
                            </td>

                            <td className="border p-3">

                                <span className={tier.className}>
                                    {tier.label}
                                </span>

                            </td>

                        </tr>

                        );

                    })}

            </tbody>

        </table>

        </div >

    );

}
