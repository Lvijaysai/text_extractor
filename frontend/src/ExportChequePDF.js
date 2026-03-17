// frontend/src/ExportChequePDF.js
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

export const downloadChequeValidationPDF = (result) => {
  const doc = new jsPDF();

  const validation = result?.data?.validation_details || {};
  const finalDecision = result?.data?.final_decision || "N/A";
  const timestamp = result?.timestamp || "N/A";

  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text("Cheque Validation Report", 14, 18);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(`Generated At: ${timestamp}`, 14, 26);
  doc.text(`Final Decision: ${finalDecision}`, 14, 32);

  const rows = [
    ["Account Exists", validation.account_exists ? "Yes" : "No"],
    ["PAN Owner Match", validation.pan_owner_match ? "Yes" : "No"],
    ["Payee Aadhaar Match", validation.payee_aadhaar_match ? "Yes" : "No"],
    ["Signature Verified", validation.signature_verified ? "Yes" : "No"],
  ];

  autoTable(doc, {
    startY: 40,
    head: [["Field", "Value"]],
    body: rows,
    theme: "grid",
    styles: {
      fontSize: 10,
      cellPadding: 4,
      lineColor: [180, 180, 180],
      lineWidth: 0.2,
    },
    headStyles: {
      fillColor: [41, 128, 185],
      textColor: 255,
      fontStyle: "bold",
    },
    columnStyles: {
      0: { fontStyle: "bold", cellWidth: 75 },
      1: { cellWidth: 95 },
    },
    margin: { top: 40 },
  });

  const pageCount = doc.internal.getNumberOfPages();
  doc.setFontSize(8);

  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.text(`Page ${i} of ${pageCount}`, 196, 285, { align: "right" });
  }

  const safeDecision = String(finalDecision).replace(/\s+/g, "_");
  doc.save(`Cheque_Validation_Report_${safeDecision}.pdf`);
};