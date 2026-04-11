import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadSimple, FileArrowUp } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { Progress } from './ui/progress';

const UploadZone = ({ onUpload, isUploading, uploadProgress }) => {
  const [isDragActive, setIsDragActive] = useState(false);

  const onDrop = useCallback((acceptedFiles) => {
    onUpload(acceptedFiles);
  }, [onUpload]);

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp']
    },
    multiple: true,
    onDragEnter: () => setIsDragActive(true),
    onDragLeave: () => setIsDragActive(false),
    onDropAccepted: () => setIsDragActive(false),
    onDropRejected: () => setIsDragActive(false)
  });

  return (
    <div
      {...getRootProps()}
      data-testid="upload-dropzone"
      className={`tracing-beam-border ${
        isDragActive ? 'active' : ''
      } relative min-h-[320px] flex flex-col items-center justify-center p-8 bg-card cursor-pointer hover:border-primary/70 transition-colors`}
    >
      <input {...getInputProps()} />
      
      <AnimatePresence>
        {isUploading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="scanning-line"
          />
        )}
      </AnimatePresence>

      <motion.div
        animate={{
          scale: isDragActive ? 1.05 : 1,
        }}
        className="text-center"
      >
        {isUploading ? (
          <FileArrowUp size={64} weight="duotone" className="mx-auto mb-4 text-primary" />
        ) : (
          <UploadSimple size={64} weight="duotone" className="mx-auto mb-4 text-muted-foreground" />
        )}

        <h3 className="text-xl font-semibold mb-2 tracking-tight">
          {isUploading ? 'Processing...' : 'Upload Bill Images'}
        </h3>
        
        <p className="text-sm text-muted-foreground mb-6 max-w-md">
          {isUploading
            ? 'Analyzing your documents...'
            : 'Drag & drop bill images here, or click to select files. Supports JPEG, PNG, WEBP.'}
        </p>

        {isUploading ? (
          <div className="w-full max-w-md mx-auto space-y-2">
            <Progress value={uploadProgress} className="h-1" />
            <p className="terminal-text text-xs text-muted-foreground">
              {uploadProgress < 50 ? 'Uploading images...' : uploadProgress < 100 ? 'Processing files...' : 'Complete'}
            </p>
          </div>
        ) : (
          <Button
            type="button"
            data-testid="upload-select-button"
            className="bg-primary hover:bg-primary/90 text-primary-foreground"
          >
            Select Files
          </Button>
        )}
      </motion.div>
    </div>
  );
};

export default UploadZone;