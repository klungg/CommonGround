import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { ProjectService } from '@/lib/api';
import Image from 'next/image';

interface Metadata {
  title: string;
  description: string;
  image: string;
  favicon: string;
  domain: string;
}

interface OpenGraphCardProps {
  url: string;
}

export function OpenGraphCard({ url }: OpenGraphCardProps) {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        setIsLoading(true);
        const data = (await ProjectService.getMetadata({ url })) as unknown as Metadata;
        setMetadata(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error fetching metadata');
      } finally {
        setIsLoading(false);
      }
    };

    fetchMetadata();
  }, [url]);

  if (isLoading) {
    return (
      <Card className="w-full h-full animate-pulse bg-gray-100">
        <div className="flex items-center justify-center h-full">
          <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
        </div>
      </Card>
    );
  }

  if (error || !metadata) {
    return (
      <Card className="w-full h-full p-4 hover:bg-gray-50 transition-colors">
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
          {url}
        </a>
      </Card>
    );
  }

  return (
    <Card className="w-full h-full overflow-hidden hover:bg-gray-50 transition-colors">
      <a href={url} target="_blank" rel="noopener noreferrer" className="block p-4 h-full flex flex-col justify-between">
          <h3 className="font-bold text-[13px] line-clamp-2">{metadata.title}</h3>
          {metadata.description && (
            <p className="text-[12px] text-[#555555] line-clamp-2">{metadata.description}</p>
          )}
          <div className="flex items-center gap-2">
            <Image src={metadata.favicon} alt="" width={20} height={20} />
            <span className="text-[13px] text-[#676767]">{metadata.domain}</span>
          </div>
      </a>
    </Card>
  );
} 