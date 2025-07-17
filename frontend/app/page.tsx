import ChatPage from './chat/page';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Chat',
};

export default function HomePage() {
  return <ChatPage />;
}
