'use client';

import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download, FileUp, Loader2, RefreshCcw, ClipboardCopy } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';

type ConversionStatus = 'idle' | 'processing' | 'success' | 'error';

interface PdfAgentResponse {
  status: string;
  data?: {
    file_name: string;
    draft_markdown: string;
    final_markdown: string;
    step1_model: string;
    step2_model: string;
  };
  message?: string;
}

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? '/webview';

export default function PdfToMarkdownPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [conversionStatus, setConversionStatus] = useState<ConversionStatus>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [draftMarkdown, setDraftMarkdown] = useState<string>('');
  const [finalMarkdown, setFinalMarkdown] = useState<string>('');
  const [fileName, setFileName] = useState<string>('');

  const isProcessing = conversionStatus === 'processing';

  const formattedStatus = useMemo(() => {
    switch (conversionStatus) {
      case 'processing':
        return statusMessage || 'Running two-step Gemini conversion…';
      case 'success':
        return 'Markdown ready';
      case 'error':
        return errorMessage || 'Conversion failed';
      default:
        return 'Awaiting upload';
    }
  }, [conversionStatus, statusMessage, errorMessage]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
    setFileName(file.name);
    setConversionStatus('idle');
    setDraftMarkdown('');
    setFinalMarkdown('');
    setErrorMessage('');
  };

  const resetState = () => {
    setSelectedFile(null);
    setConversionStatus('idle');
    setStatusMessage('');
    setErrorMessage('');
    setDraftMarkdown('');
    setFinalMarkdown('');
    setFileName('');
  };

  const apiEndpoint = useMemo(() => `${BASE_PATH.replace(/\/$/, '')}/api/pdf-to-markdown`, []);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Please choose a PDF before converting.');
      setConversionStatus('error');
      return;
    }

    setConversionStatus('processing');
    setStatusMessage('Uploading PDF…');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('file', selectedFile, selectedFile.name);

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        body: formData,
      });

      setStatusMessage('Awaiting Gemini responses…');

      const json = (await response.json()) as PdfAgentResponse;

      if (!response.ok || json.status !== 'success' || !json.data) {
        const message = json.message || 'The PDF agent was unable to process this file.';
        setErrorMessage(message);
        setConversionStatus('error');
        return;
      }

      setDraftMarkdown(json.data.draft_markdown || '');
      setFinalMarkdown(json.data.final_markdown || '');
      setFileName(json.data.file_name || selectedFile.name);
      setConversionStatus('success');
      setStatusMessage('');
    } catch (error) {
      console.error('PDF conversion failed', error);
      setErrorMessage('A network error prevented the conversion.');
      setConversionStatus('error');
    }
  };

  const handleDownload = () => {
    const blob = new Blob([finalMarkdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName ? fileName.replace(/\.pdf$/i, '.md') : 'document.md';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    if (!finalMarkdown) {
      return;
    }
    try {
      await navigator.clipboard.writeText(finalMarkdown);
      setStatusMessage('Copied Markdown to clipboard.');
      setTimeout(() => setStatusMessage(''), 2500);
    } catch (error) {
      console.error('Failed to copy Markdown', error);
      setErrorMessage('Copy failed. Please try manually.');
      setConversionStatus('error');
    }
  };

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">PDF → Markdown Agent</h1>
        <p className="text-muted-foreground">
          Run a dedicated two-step Gemini workflow that first extracts raw text from your PDF and then refines it into production-ready Markdown—no local OCR required.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Upload PDF</CardTitle>
            <CardDescription>Files up to 10&nbsp;MB are supported.</CardDescription>
          </CardHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="pdf-file">PDF file</Label>
                <Input
                  id="pdf-file"
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileChange}
                  disabled={isProcessing}
                />
              </div>
              {selectedFile && (
                <p className="text-sm text-muted-foreground">
                  Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)}&nbsp;MB)
                </p>
              )}
              <Separator />
              <div className="space-y-2 text-sm">
                <p className="font-medium">Two-step process</p>
                <ol className="list-decimal space-y-1 pl-4 text-muted-foreground">
                  <li>Gemini extracts plain text from the PDF.</li>
                  <li>The draft and original PDF are re-sent to Gemini for Markdown formatting.</li>
                </ol>
              </div>
            </CardContent>
            <CardFooter className="flex flex-col gap-2 sm:flex-row">
              <Button type="submit" disabled={isProcessing || !selectedFile} className="flex-1">
                {isProcessing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Converting…
                  </>
                ) : (
                  <>
                    <FileUp className="mr-2 h-4 w-4" />
                    Convert PDF
                  </>
                )}
              </Button>
              <Button type="button" variant="ghost" disabled={isProcessing} onClick={resetState} className="flex-1">
                <RefreshCcw className="mr-2 h-4 w-4" />
                Reset
              </Button>
            </CardFooter>
          </form>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="space-y-2">
            <CardTitle>Conversion Output</CardTitle>
            <CardDescription className={conversionStatus === 'error' ? 'text-destructive' : ''}>
              {formattedStatus}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid flex-1 gap-6 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">Step 1 draft</h3>
                <span className="text-xs text-muted-foreground">Plain text from Gemini</span>
              </div>
              <Textarea value={draftMarkdown} readOnly className="h-64 resize-none bg-muted" placeholder="Draft Markdown will appear here." />
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">Final Markdown</h3>
                <div className="flex items-center gap-2">
                  <Button type="button" size="icon" variant="outline" disabled={!finalMarkdown} onClick={handleCopy}>
                    <ClipboardCopy className="h-4 w-4" />
                    <span className="sr-only">Copy Markdown</span>
                  </Button>
                  <Button type="button" size="icon" variant="outline" disabled={!finalMarkdown} onClick={handleDownload}>
                    <Download className="h-4 w-4" />
                    <span className="sr-only">Download Markdown</span>
                  </Button>
                </div>
              </div>
              <Textarea value={finalMarkdown} readOnly className="h-64 resize-none" placeholder="Refined Markdown will appear here." />
            </div>
          </CardContent>
          <Separator className="my-4" />
          <CardFooter className="block">
            <h4 className="mb-2 text-sm font-semibold">Preview</h4>
            <div className="prose prose-sm max-w-none rounded-md border bg-background p-4 dark:prose-invert">
              {finalMarkdown ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{finalMarkdown}</ReactMarkdown>
              ) : (
                <p className="text-sm text-muted-foreground">The formatted Markdown preview will appear here after conversion.</p>
              )}
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
