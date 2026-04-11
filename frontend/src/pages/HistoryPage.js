import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Badge } from '../components/ui/badge';
import { DownloadSimple, Eye, FilePdf, Translate } from '@phosphor-icons/react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const HistoryPage = () => {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBill, setSelectedBill] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [originalImage, setOriginalImage] = useState('');

  useEffect(() => {
    fetchBills();
  }, []);

  const fetchBills = async () => {
    try {
      const response = await axios.get(`${API}/bills`);
      setBills(response.data);
    } catch (error) {
      console.error('Failed to fetch bills:', error);
      toast.error('Failed to load translation history');
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (bill) => {
    try {
      const imageResponse = await axios.get(`${API}/bills/${bill.id}/image`);
      setOriginalImage(imageResponse.data.image_base64);
      setSelectedBill(bill);
      setViewerOpen(true);
    } catch (error) {
      console.error('Failed to load bill details:', error);
      toast.error('Failed to load bill details');
    }
  };

  const handleDownloadPDF = async (billId, filename) => {
    try {
      const response = await axios.get(`${API}/bills/${billId}/pdf`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `translated_${filename.replace(/\.[^/.]+$/, '')}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('PDF downloaded successfully!');
    } catch (error) {
      console.error('Download error:', error);
      toast.error('Failed to download PDF');
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      uploaded: { variant: 'secondary', label: 'Uploaded' },
      processing: { variant: 'default', label: 'Processing' },
      translated: { variant: 'default', label: 'Translated', className: 'bg-[#00875A] text-white' },
      failed: { variant: 'destructive', label: 'Failed' },
    };

    const config = variants[status] || variants.uploaded;
    
    return (
      <Badge
        variant={config.variant}
        className={`status-badge ${config.className || ''}`}
        data-testid={`status-badge-${status}`}
      >
        {config.label}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96" data-testid="history-loading">
        <div className="terminal-text text-muted-foreground">Loading translation history...</div>
      </div>
    );
  }

  if (bills.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96" data-testid="history-empty">
        <img
          src="https://static.prod-images.emergentagent.com/jobs/7504f9e0-890e-457d-bcbf-ed056fcb5564/images/8365c21bdc5adc579a401d5ae4c1932033eefc4b32850804e1e5e50b6ecaab8c.png"
          alt="No bills"
          className="w-64 h-64 object-contain mb-6 opacity-50"
        />
        <h3 className="text-xl font-semibold mb-2 tracking-tight" style={{ color: '#0A0A0A' }}>No Translation History</h3>
        <p className="text-sm" style={{ color: '#525252' }}>Upload your first bill to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="history-page">
      <div className="pb-4" style={{ borderBottom: '1px solid #E5E5E5' }}>
        <h1 className="text-4xl font-bold tracking-tighter" style={{ color: '#0A0A0A' }}>Translation History</h1>
        <p className="text-sm mt-2" style={{ color: '#525252' }}>View and download all your translated bills</p>
      </div>

      <div className="border" style={{ backgroundColor: '#FFFFFF', borderColor: '#E5E5E5' }}>
        <Table>
          <TableHeader>
            <TableRow className="border-b border-border hover:bg-transparent">
              <TableHead className="text-xs uppercase tracking-[0.2em]">Date</TableHead>
              <TableHead className="text-xs uppercase tracking-[0.2em]">Filename</TableHead>
              <TableHead className="text-xs uppercase tracking-[0.2em]">Language</TableHead>
              <TableHead className="text-xs uppercase tracking-[0.2em]">Status</TableHead>
              <TableHead className="text-xs uppercase tracking-[0.2em] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bills.map((bill) => (
              <TableRow key={bill.id} className="border-b border-border" data-testid={`bill-row-${bill.id}`}>
                <TableCell className="terminal-text text-sm">
                  {new Date(bill.upload_date).toLocaleDateString()}
                </TableCell>
                <TableCell className="font-medium">{bill.filename}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="status-badge">
                    {bill.original_language}
                  </Badge>
                </TableCell>
                <TableCell>{getStatusBadge(bill.status)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex gap-2 justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleView(bill)}
                      data-testid={`view-bill-${bill.id}`}
                      className="gap-2"
                    >
                      <Eye size={16} />
                      View
                    </Button>
                    {bill.status === 'translated' && (
                      <Button
                        size="sm"
                        onClick={() => handleDownloadPDF(bill.id, bill.filename)}
                        data-testid={`download-pdf-${bill.id}`}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
                      >
                        <DownloadSimple size={16} weight="bold" />
                        PDF
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Viewer Dialog */}
      <Dialog open={viewerOpen} onOpenChange={setViewerOpen}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto" data-testid="viewer-modal">
          <DialogHeader>
            <DialogTitle className="text-2xl tracking-tight">{selectedBill?.filename}</DialogTitle>
            <DialogDescription>
              <span className="terminal-text">
                {selectedBill?.original_language} → English | {new Date(selectedBill?.upload_date || '').toLocaleString()}
              </span>
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
            {/* Original Image */}
            <div className="border border-border p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3 flex items-center gap-2">
                <FilePdf size={16} />
                Original Bill
              </div>
              {originalImage && (
                <img
                  src={`data:image/jpeg;base64,${originalImage}`}
                  alt="Original bill"
                  className="w-full border border-border"
                  data-testid="original-image"
                />
              )}
            </div>

            {/* Translated Text */}
            <div className="border border-border p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3 flex items-center gap-2">
                <Translate size={16} />
                Translated Content
              </div>
              <div className="prose prose-sm max-w-none" data-testid="translated-text">
                <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                  {selectedBill?.translated_text || 'No translation available'}
                </pre>
              </div>
            </div>
          </div>

          {selectedBill?.status === 'translated' && (
            <div className="flex justify-end mt-4">
              <Button
                onClick={() => handleDownloadPDF(selectedBill.id, selectedBill.filename)}
                data-testid="download-pdf-modal-btn"
                className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
              >
                <DownloadSimple size={20} weight="bold" />
                Download PDF
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default HistoryPage;