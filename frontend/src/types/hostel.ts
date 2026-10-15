export interface RoomInfo {
  id: number;
  number: string;
  floor: number;
  floor_label: string;
  wing: string;
}

export interface LocationInfo {
  id: number;
  kind: 'FLOOR_WING' | 'GROUND_FACILITY';
  floor: number;
  wing: string | null;
  facility_name: string | null;
  label: string;
}

export interface WingNode {
  id: number;
  code: string;
  rooms: { id: number; number: string }[];
}

export interface FloorNode {
  id: number;
  number: number;
  label: string;
  wings: WingNode[];
  facilities: LocationInfo[];
}

export interface HostelStructure {
  id: number;
  code: string;
  name: string;
  floors: FloorNode[];
}
