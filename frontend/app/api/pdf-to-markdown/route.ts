import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function POST(request: NextRequest) {
  const incomingForm = await request.formData();
  const file = incomingForm.get('file');

  if (!(file instanceof File)) {
    return NextResponse.json({ status: 'error', message: 'No PDF file provided.' }, { status: 400 });
  }

  const forwardForm = new FormData();
  forwardForm.append('file', file, file.name);

  let response: Response;
  try {
    response = await fetch(`${BACKEND_BASE_URL}/pdf/to-markdown`, {
      method: 'POST',
      body: forwardForm,
    });
  } catch (error) {
    console.error('Failed to connect to backend PDF agent:', error);
    return NextResponse.json(
      { status: 'error', message: 'Unable to reach PDF service.' },
      { status: 502 },
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok || !data) {
    const message = data?.detail ?? data?.message ?? 'PDF conversion failed.';
    return NextResponse.json(
      { status: 'error', message },
      { status: response.status || 500 },
    );
  }

  return NextResponse.json(data, { status: response.status });
}
