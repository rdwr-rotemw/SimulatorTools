export interface DeviceTemplateGeneral {
  name?: string;
  multi_home?: string;
  dhcp?: string;
  subnet_mask?: string;
  mac_address?: string;
  interface?: string;
  user_data?: string;
  topology_data?: string;
  display_tag?: string;
  modeling_file?: string;
  common_data_file?: string;
}

export interface DeviceTemplateSnmp {
  read_community?: string;
  write_community?: string;
  mib_file?: string;
  agent_file?: string;
  trap_mgr?: string;
  snmp_str?: string;
  response_delay?: string;
  mtu_size?: string;
  snmp_port?: string;
  security_level?: string;
  user_name?: string;
}

export interface DeviceTemplateSoap {
  soap_http_port?: string;
  soap_https_port?: string;
  xml_https_type?: string;
  soap_mod_file?: string;
  soap_content_type?: string;
}

export interface DeviceTemplateSSH {
  ssh_user_name?: string;
  ssh_password?: string;
  ssh_scp_base_dir?: string;
  ssh_version?: string;
  ssh_file?: string;
}

export interface DeviceTemplateDevice {
  general?: DeviceTemplateGeneral;
  snmp?: DeviceTemplateSnmp;
  soap?: DeviceTemplateSoap;
  ssh?: DeviceTemplateSSH;
}

export interface DeviceTemplateStructure {
  device_map?: {
    release?: string;
    description?: string;
    user_data?: string;
    setup_file?: string;
    interface?: string;
    separator?: string;
    start_interface_num?: string;
    username?: string;
    device?: DeviceTemplateDevice;
  };
}

export interface DeviceTemplate {
  _id: string;
  name: string;
  description?: string;
  template: DeviceTemplateStructure;
  created_at: string;
  updated_at?: string;
}

export interface DeviceTemplateCreate {
  name: string;
  description?: string;
  template: DeviceTemplateStructure;
}

export interface DeviceTemplateUpdate {
  name?: string;
  description?: string;
  template?: DeviceTemplateStructure;
}

