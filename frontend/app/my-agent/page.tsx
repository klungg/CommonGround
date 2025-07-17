'use client';

import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Plus, SquarePen, Star } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";

export default function MyAgentPage() {
  return (
    <div className="h-screen">
      <div className="flex flex-col h-screen">
        {/* Navigation Bar */}
        <div className="flex-shrink-0 h-14 flex items-center justify-between px-4">
          <SidebarTrigger />
        </div>

        <div className="flex-1 p-6">
          <div className="max-w-[672px] mx-auto">
            <h1 className="text-[32px] font-medium mb-8">My Agent</h1>
            
            {/* Agent List Container */}
            <div className="space-y-3">
              {/* General an Agent Button */}
              <Button 
                variant="outline" 
                className="w-full flex items-center justify-between p-4 min-h-[72px] bg-white rounded-lg border border-[#E4E4E4] hover:border-[#D4D4D4] transition-colors font-normal"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-sm border border-[#E4E4E7] flex items-center justify-center">
                    <Plus className="h-3 w-3" />
                  </div>
                  <span className="text-lg font-medium">General an Agent</span>
                </div>
              </Button>

              {/* Agent List */}
              {[1, 2, 3].map((index) => (
                <div key={index} className="flex items-center justify-between p-4 min-h-[72px] bg-white rounded-lg border border-[#E4E4E4] hover:border-[#D4D4D4] transition-colors">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8 bg-gray-100">
                      <AvatarFallback>J</AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">Associate_WebSearcher</span>
                        <Star className="h-4 w-4 text-yellow-400" />
                      </div>
                      <p className="text-sm text-gray-500">Associate agent specialized in web searching tasks.</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="icon" className="self-start h-8 w-8">
                    <SquarePen className="h-4 w-4 text-[#979797]" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 