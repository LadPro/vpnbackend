import boto3
import subprocess
import time
import threading
import os
import sqlite3
import json

regiones = {"india":"ap-south-1",
"suecia":"eu-north-1",
"francia":"eu-west-3",
"inglaterra":"eu-west-2",
"irlanda":"eu-west-1",
"corea":"ap-northeast-2",
"japon":"ap-northeast-1",
"canada":"ca-central-1",
"brasil":"sa-east-1",
"singapur":"ap-southeast-1",
"australia":"ap-southeast-2",
"alemania":"eu-central-1",
"us":"us-east-1",}

############################################Varibles
script_dir = os.path.dirname(__file__)
# actual = "us"
instancetype = ['t3.micro','t2.micro']
keypub = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCxMEo7XjvUVFug45TGA4k3rM5iiil1R35B+gQmNBAoy9ithQITlOtuE93HQNLnqGKnOl83kLKHRaymTNwM6gNusyUIuNuj6hXYtCdygFphBsoPZ3+W2dtRZ3hjpl59MfAbHHkd+2u5RMJXjt9jrhFer/FhyZ6x6S5B4+yIVI4JLCrJ3pnRvifbrisOAWhd4von55ewlBQKelNc6DNNjbL/tSTSQluf48tzcrwz21RItQRxwTASrehL6zrAZRncrSjPF61Shef6ce8ohNIQHmD1zSBWxWIPF2krlRW36nCJrTgxCuNHVzY60bn8diy+ZdeTONzrEK33CmsTW0Pv8Q35"
ami_description = 'Amazon Linux 2023 AMI 2023.2.20231030.1 x86_64 HVM kernel-6.1'
sg_stack_body = ""
vpn_stack_body = ""
sg_stack_path = f"{script_dir}/sg.yaml"   ### direccion del stack del security group
vpn_stack_path = f"{script_dir}/vpnstack.yaml"  ##direccion del stack de ec2
private_key = f'{script_dir}/vpn.pem'   ### direccion de la private key
db_dir = f'{script_dir}/datos.db'

###guardar templates en variables
# def templates (sg_stack_path, vpn_stack_path):
#     global sg_stack_body, vpn_stack_body
#template sg
with open (sg_stack_path, "r") as sg_stack_file:
    sg_stack_body = sg_stack_file.read()
#template ec2
with open (vpn_stack_path, "r") as vpn_stack_file:
    vpn_stack_body = vpn_stack_file.read()

def seleccionar_region (reg="us"):
    # global ec2
    # global cloudformation
    # global actual
    actual = reg
    region = regiones[reg]
    session = boto3.Session(region_name=region,)
    ec2 = session.client("ec2")
    cloudformation = session.client("cloudformation")
    return {"region":actual, "ec2":ec2, "cloudformation":cloudformation}
##crear key par
def crearkeypar (reg="us"):
    client = seleccionar_region (reg)
    keypairs = client['ec2'].describe_key_pairs()
    keypar = next((key for key in keypairs['KeyPairs'] if key['KeyName']=='vpn'),None)
    # print(keypar)
    if keypar is None:
        response = client['ec2'].import_key_pair(KeyName='vpn', PublicKeyMaterial=keypub)
        
########################################tipo de isntancia
##buscar tipo de instancia devulve el tipo de instancia
def buscar_tipo_instacia (reg="us"):
    client = seleccionar_region(reg)
    instancia = ""
    typei = [] 
    for a in instancetype:
        try:
            instancia = client['ec2'].describe_instance_types(
                InstanceTypes=[a],
                Filters=[{'Name': 'free-tier-eligible','Values': ['true']}]
                )
            # print(instancia['InstanceTypes'][0]['FreeTierEligible'])
            if instancia['InstanceTypes'][0]['FreeTierEligible']:
                typei.append(instancia['InstanceTypes'])
        except Exception as e:
            print (e)
    if typei != []:
        ins_type = typei[0][0]['InstanceType']
        return ins_type
    else:
        print (f'los tipos de instancias seleccionado no son freetier para esta cuenta :{instancetype}')
        return instancetype[0]

###############################################security group
##buscar sg id
def buscar_sgid (reg="us"):
    client = seleccionar_region (reg)
    vpcs = client['ec2'].describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}]) #obtener id vpc default
    default_vpc_id = vpcs["Vpcs"][0]["VpcId"]                                     #obtener id vpc default
    sgs = client['ec2'].describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])
    vpn_sg_id = next((sg for sg in sgs['SecurityGroups'] if sg['GroupName'] == "vpn_sg"), None)
    ##crear sg si no existe
    if vpn_sg_id is None:
        response = client['cloudformation'].create_stack(
            StackName='sgVpn',
            TemplateBody=sg_stack_body,
            Parameters=[
                {'ParameterKey': "VpcId",'ParameterValue': default_vpc_id,},
            ],
            OnFailure='ROLLBACK',
        )
        waiter = client['cloudformation'].get_waiter('stack_create_complete')
        waiter.wait(
            StackName=response['StackId'],
        )
        stack_descripcion = client['cloudformation'].describe_stacks(StackName="sgVpn")
        return stack_descripcion["Stacks"][0]['Outputs'][0]['OutputValue']
        # print (vpn_sg_id)
    else:
        return vpn_sg_id['GroupId']

#####################################ami id
#buscar ami id 
def buscar_amiid (reg="us"):
    #global ami_id
    client = seleccionar_region(reg)
    amis = client['ec2'].describe_images(
        Filters=[
            {'Name': 'owner-alias','Values': ['amazon']},
            {'Name': 'description','Values': [ami_description]},
            {'Name': 'state','Values': ['available']}
        ],
        Owners=['amazon']
    )
    amis['Images'].sort(key=lambda x: x['CreationDate'], reverse=True)
    ami_id = amis['Images'][0] if amis['Images'] else None
    return ami_id['ImageId']
    # print (ami_id)


###########lanzar stack de ec2
#buscar si stack esta creado
#def buscar_stack_id():
    
def crear_stack (vpn_sg_id, ami_id, ins_type, reg="us"):
    client = seleccionar_region(reg)
    stack = client['cloudformation'].create_stack(
        StackName='ec2vpn',
        TemplateBody=vpn_stack_body,
        Parameters=[
            {   'ParameterKey': "SgId",
                'ParameterValue': vpn_sg_id,},
            {   'ParameterKey': "AmiId",
                'ParameterValue': ami_id,},
            {   'ParameterKey': "TypeIns",
                'ParameterValue': ins_type,},
        ],
        OnFailure='ROLLBACK',
    )
    waiter = client['cloudformation'].get_waiter('stack_create_complete')
    waiter.wait(
        StackName=stack['StackId'],
    )
    return stack


def buscar_stack (reg):
    client = seleccionar_region(reg)
    stack_descripcion = client['cloudformation'].describe_stacks()
    stack_vpn = next((st for st in stack_descripcion['Stacks'] if st['StackName'] == "ec2vpn"), None)
    # if stack_vpn == None:
    #     print("stack no creado")
    # else:
    #     print("stack ya creado")
    return stack_vpn

def eliminar_stack (reg="us", waiter=True):
        client = seleccionar_region(reg)
        client['cloudformation'].delete_stack(StackName='ec2vpn',)
        if waiter:
            waiter_delete = client['cloudformation'].get_waiter('stack_delete_complete')
            # stack_descripcion = cloudformation.describe_stacks()
            waiter_delete.wait(StackName='ec2vpn',)
        eliminar_conf(reg)

def eliminar_conf(ruta="us"):
    direccion = f'{script_dir}/{ruta}.conf'
    try:
        os.remove(direccion)
        print(f"Archivo {direccion} eliminado exitosamente.")
    except OSError as e:
        print(f"Error al eliminar el archivo {direccion}: {e}")

def obtener_ip (reg):
    stack = buscar_stack(reg)
    if stack == None:
        print("no creado")
        return stack
    else:
        ip = stack['Outputs'][0]['OutputValue']
        return ip

def extraer_conf(ip, region, intentos_maximos=3, tiempo_espera=60):
    source_path = f'ec2-user@{ip}:/home/wireguard/config/peer1/peer1.conf'
    destination_path = f'./{region}.conf'

    scp_command = ['scp', '-i',  private_key, '-o', 'StrictHostKeyChecking=no', source_path, destination_path]
    def transferencia():
        intentos = 0
        while intentos < intentos_maximos:
            try:
                subprocess.run(scp_command, check=True)
                print("Transferencia exitosa")
                break  # Sal del bucle si la transferencia es exitosa
            except subprocess.CalledProcessError as e:
                print(f"Error en la transferencia: {e}")
                intentos += 1
                if intentos < intentos_maximos:
                    print(f"Reintentando en {tiempo_espera} segundos...")
                    time.sleep(tiempo_espera)
        
        if intentos == intentos_maximos:
            print(f"Se agotaron los intentos. La transferencia no fue exitosa.")

    # Crear un hilo para ejecutar la función en segundo plano
    hilo = threading.Thread(target=transferencia)
    
    # Iniciar el hilo
    hilo.start()
        
def crear_vpn (reg):
    #condicional si no esta creado
    crearkeypar (reg) 
    vpn_sg_id = buscar_sgid(reg)
    ami_id = buscar_amiid(reg)
    ins_type = buscar_tipo_instacia(reg)                     
    stack_vpn = buscar_stack (reg)
    stack = ""
    if stack_vpn == None:
        stack = crear_stack(vpn_sg_id, ami_id, ins_type, reg)
    else:
        #eliminado stack
        eliminar_stack (reg)
        #creando stack
        stack = crear_stack(vpn_sg_id, ami_id, ins_type, reg)
    ip = obtener_ip (reg)
    extraer_conf(ip, reg)
    return stack

#### buscar todas las vpn
def buscar_todas ():
    las_regiones = {}
    for region in regiones:
        stack = buscar_stack(region)
        las_regiones[region] = stack
    return las_regiones

def apagar_todas():
    for region in regiones:
        stack = buscar_stack(region)
        if stack != None:
            eliminar_stack(region,False)
            print(region)

def encender_todas():
    for region in regiones:
        stack = buscar_stack(region)
        if stack == None:
            crear_vpn(region)
            print(region)

def regular_conf():
    regiones = buscar_todas()
    for region in regiones:
        if regiones[region] == None:
            eliminar_conf(region)
        else:
            ip = regiones[region]['Outputs'][0]['OutputValue']
            print(ip)
            extraer_conf(ip)
    return regiones



def crear_db ():
    try:
        conn = sqlite3.connect(db_dir)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE recursos (
                config TEXT PRIMARY KEY,
                llave TEXT,
                ami TEXT,
                recursos TEXT
            )
        ''')
        llave = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCxMEo7XjvUVFug45TGA4k3rM5iiil1R35B+gQmNBAoy9ithQITlOtuE93HQNLnqGKnOl83kLKHRaymTNwM6gNusyUIuNuj6hXYtCdygFphBsoPZ3+W2dtRZ3hjpl59MfAbHHkd+2u5RMJXjt9jrhFer/FhyZ6x6S5B4+yIVI4JLCrJ3pnRvifbrisOAWhd4von55ewlBQKelNc6DNNjbL/tSTSQluf48tzcrwz21RItQRxwTASrehL6zrAZRncrSjPF61Shef6ce8ohNIQHmD1zSBWxWIPF2krlRW36nCJrTgxCuNHVzY60bn8diy+ZdeTONzrEK33CmsTW0Pv8Q35'
        ami = "Amazon Linux 2023 AMI 2023.2.20231030.1 x86_64 HVM kernel-6.1"
        recursos = str({'india': None, 'suecia': None, 'francia': None, 'inglaterra': None, 'irlanda': None, 'corea': None, 'japon': None, 'canada': None, 'brasil': None, 'singapur': None, 'australia': None, 'alemania': None, 'us': None})

        cursor.execute('INSERT INTO recursos VALUES (?, ?, ?, ?)', ("config", llave, ami, recursos))
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)

def consultar ():
    conn = sqlite3.connect(db_dir)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recursos WHERE config = ?",("config",))        
    resultado = cursor.fetchone()
    return resultado

def update (dato, columna):
    conn = sqlite3.connect(db_dir)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE recursos SET {columna} = ? WHERE config = ?", (dato, "config"))        
    conn.commit()
    conn.close()

def ontode():
    time.sleep(5)
    consulta = consultar()
    
    consulta = consulta[3]
    consulta = eval(consulta)
    for con in consulta:
        consulta[con]="noNone"
    # consulta["a"]= a
    #print(consulta)
    consulta_str = str(consulta)
    update(consulta_str, "recursos")
    return consulta

def offtode():
    time.sleep(5)
    consulta = consultar()
    
    consulta = consulta[3]
    consulta = eval(consulta)
    for con in consulta:
        consulta[con]=None
    # consulta["a"]= a
    #print(consulta)
    consulta_str = str(consulta)
    update(consulta_str, "recursos")
    
    return consulta

def actua():
    time.sleep(5)
    consulta = consultar()
    
    consulta = consulta[3]
    consulta = eval(consulta)
       
    return consulta

def onuna(a):
    time.sleep(5)
    consulta = consultar()
    
    consulta = consulta[3]
    consulta = eval(consulta)
    consulta[a]="noNone"
    # consulta["a"]= a
    #print(consulta)
    consulta_str = str(consulta)
    update(consulta_str, "recursos")
    return consulta
# conn = sqlite3.connect(db_dir)
# cursor = conn.cursor()

# # Insertar datos en la tabla
# llave = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCxMEo7XjvUVFug45TGA4k3rM5iiil1R35B+gQmNBAoy9ithQITlOtuE93HQNLnqGKnOl83kLKHRaymTNwM6gNusyUIuNuj6hXYtCdygFphBsoPZ3+W2dtRZ3hjpl59MfAbHHkd+2u5RMJXjt9jrhFer/FhyZ6x6S5B4+yIVI4JLCrJ3pnRvifbrisOAWhd4von55ewlBQKelNc6DNNjbL/tSTSQluf48tzcrwz21RItQRxwTASrehL6zrAZRncrSjPF61Shef6ce8ohNIQHmD1zSBWxWIPF2krlRW36nCJrTgxCuNHVzY60bn8diy+ZdeTONzrEK33CmsTW0Pv8Q35'
# ami = "Amazon Linux 2023 AMI 2023.2.20231030.1 x86_64 HVM kernel-6.1"
# recursos = str({'india': None, 'suecia': None, 'francia': None, 'inglaterra': None, 'irlanda': None, 'corea': None, 'japon': None, 'canada': None, 'brasil': None, 'singapur': None, 'australia': None, 'alemania': None, 'us': None})  # Convierte el diccionario a una cadena para almacenarlo

# cursor.execute('INSERT INTO recursos VALUES (?, ?, ?)', (llave, ami, recursos))

# # Guardar cambios y cerrar la conexión
# conn.commit()
# conn.close()

# todos_stack=regular_conf()
# apagar_todas()
# todos_stack=buscar_todas ()
# stack=crear_vpn ("region")
# encender_todas()