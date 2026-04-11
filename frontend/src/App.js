import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '@/App.css';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import UploadZone from './components/UploadZone';
import HistoryPage from './pages/HistoryPage';
import { Files, ClockCounterClockwise, Gear } from '@phosphor-icons/react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Sidebar = () => {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Upload', icon: Files },
    { path: '/history', label: 'History', icon: ClockCounterClockwise },
  ];

  return (
    <div className="w-64 border-r h-screen fixed left-0 top-0 flex flex-col" style={{ backgroundColor: '#FFFFFF', borderColor: '#E5E5E5' }} data-testid="sidebar">
      <div className="p-6 border-b" style={{ borderColor: '#E5E5E5' }}>
        <h1 className="text-2xl font-bold tracking-tighter" style={{ color: '#0A0A0A' }}>BillTranslate</h1>
        <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: '#525252' }}>OCR & Translation</p>
      </div>
      
      <nav className="flex-1 p-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className="flex items-center gap-3 px-4 py-3 mb-1 transition-colors"
              style={
                isActive
                  ? { backgroundColor: '#002FA7', color: '#FFFFFF' }
                  : { color: '#0A0A0A' }
              }
              onMouseEnter={(e) => !isActive && (e.currentTarget.style.backgroundColor = '#F5F5F5')}
              onMouseLeave={(e) => !isActive && (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <Icon size={20} weight={isActive ? 'fill' : 'regular'} />
              <span className="text-sm font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t" style={{ borderColor: '#E5E5E5' }}>
        <div className="terminal-text text-xs space-y-1" style={{ color: '#525252' }}>
          <div>System: Online</div>
          <div>Engine: Gemini 3 Flash</div>
        </div>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [stats, setStats] = useState({ total: 0, recent: null });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/bills`);
      const bills = response.data;
      setStats({
        total: bills.filter(b => b.status === 'translated').length,
        recent: bills.length > 0 ? bills[0] : null
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const handleUpload = async (files) => {
    if (files.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const totalFiles = files.length;
      let completed = 0;

      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        // Upload file
        const uploadResponse = await axios.post(`${API}/bills/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        const billId = uploadResponse.data.id;
        
        // Start translation
        setUploadProgress(((completed + 0.5) / totalFiles) * 100);
        
        await axios.post(`${API}/bills/${billId}/translate`);
        
        completed++;
        setUploadProgress((completed / totalFiles) * 100);
      }

      toast.success(`${totalFiles} bill${totalFiles > 1 ? 's' : ''} translated successfully!`);
      fetchStats();
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to process bills. Please try again.');
    } finally {
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
      }, 500);
    }
  };

  return (
    <div className="space-y-6" data-testid="dashboard">
      {/* Welcome Banner */}
      <div
        className="relative p-8 border overflow-hidden"
        style={{
          backgroundColor: '#FFFFFF',
          borderColor: '#E5E5E5',
          backgroundImage: 'url(https://static.prod-images.emergentagent.com/jobs/7504f9e0-890e-457d-bcbf-ed056fcb5564/images/783f45b01ffcac3c64a8d85bcc33498fde7a1c4f2fc2d1c70813015aa2f56431.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="relative z-10 p-6 max-w-2xl" style={{ backgroundColor: 'rgba(247, 247, 247, 0.95)' }}>
          <span className="text-xs uppercase tracking-[0.2em]" style={{ color: '#525252' }}>Supply Chain Intelligence</span>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tighter mt-2 mb-3" style={{ color: '#0A0A0A' }}>
            Convert Local Language Bills
          </h1>
          <p className="text-base leading-relaxed" style={{ color: '#525252' }}>
            Upload Hindi or regional language invoices and receive accurate English translations in PDF format.
            Perfect for export documentation and supply chain management.
          </p>
        </div>
      </div>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Upload Widget - Spans 2 columns */}
        <div className="md:col-span-2">
          <UploadZone
            onUpload={handleUpload}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
          />
        </div>

        {/* Quick Stats */}
        <div className="space-y-6">
          <div className="grid-cell p-6" style={{ backgroundColor: '#FFFFFF' }} data-testid="stats-total">
            <div className="text-xs uppercase tracking-[0.2em] mb-2" style={{ color: '#525252' }}>Total Translated</div>
            <div className="text-4xl font-bold tracking-tighter" style={{ color: '#0A0A0A' }}>{stats.total}</div>
          </div>

          <div className="grid-cell p-6" style={{ backgroundColor: '#FFFFFF' }} data-testid="stats-recent">
            <div className="text-xs uppercase tracking-[0.2em] mb-2" style={{ color: '#525252' }}>Last Upload</div>
            {stats.recent ? (
              <>
                <div className="text-sm font-medium mb-1 truncate" style={{ color: '#0A0A0A' }}>{stats.recent.filename}</div>
                <div className="terminal-text text-xs" style={{ color: '#525252' }}>
                  {new Date(stats.recent.upload_date).toLocaleDateString()}
                </div>
              </>
            ) : (
              <div className="text-sm" style={{ color: '#525252' }}>No uploads yet</div>
            )}
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div
        className="relative p-8 border overflow-hidden"
        style={{
          borderColor: '#E5E5E5',
          backgroundImage: 'url(https://images.unsplash.com/photo-1673874855449-e8620ddfa867?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwxfHxwYXBlciUyMHJlY2VpcHRzJTIwYmlsbHMlMjBhY2NvdW50aW5nfGVufDB8fHx8MTc3NTkxMjkyMHww&ixlib=rb-4.1.0&q=85)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="relative z-10 p-6" style={{ backgroundColor: 'rgba(247, 247, 247, 0.95)' }}>
          <h2 className="text-2xl font-bold tracking-tight mb-6" style={{ color: '#0A0A0A' }}>How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <div className="terminal-text text-xs mb-2" style={{ color: '#002FA7' }}>STEP 01</div>
              <h3 className="font-semibold mb-2" style={{ color: '#0A0A0A' }}>Upload Bills</h3>
              <p className="text-sm" style={{ color: '#525252' }}>Drag and drop or select bill images in any format</p>
            </div>
            <div>
              <div className="terminal-text text-xs mb-2" style={{ color: '#002FA7' }}>STEP 02</div>
              <h3 className="font-semibold mb-2" style={{ color: '#0A0A0A' }}>AI Translation</h3>
              <p className="text-sm" style={{ color: '#525252' }}>OCR extracts text and translates to English</p>
            </div>
            <div>
              <div className="terminal-text text-xs mb-2" style={{ color: '#002FA7' }}>STEP 03</div>
              <h3 className="font-semibold mb-2" style={{ color: '#0A0A0A' }}>Download PDF</h3>
              <p className="text-sm" style={{ color: '#525252' }}>Get formatted PDF with translated content</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

function App() {
  return (
    <div className="App min-h-screen" style={{ backgroundColor: 'rgb(247, 247, 247)', color: 'rgb(10, 10, 10)' }}>
      <BrowserRouter>
        <Sidebar />
        <main className="ml-64 p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;