import boto3
import subprocess
import time
import threading
import os

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

actual = "us"
instancetype = ['t3.micro','t2.micro']
keypub = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCxMEo7XjvUVFug45TGA4k3rM5iiil1R35B+gQmNBAoy9ithQITlOtuE93HQNLnqGKnOl83kLKHRaymTNwM6gNusyUIuNuj6hXYtCdygFphBsoPZ3+W2dtRZ3hjpl59MfAbHHkd+2u5RMJXjt9jrhFer/FhyZ6x6S5B4+yIVI4JLCrJ3pnRvifbrisOAWhd4von55ewlBQKelNc6DNNjbL/tSTSQluf48tzcrwz21RItQRxwTASrehL6zrAZRncrSjPF61Shef6ce8ohNIQHmD1zSBWxWIPF2krlRW36nCJrTgxCuNHVzY60bn8diy+ZdeTONzrEK33CmsTW0Pv8Q35"
ami_description = 'Amazon Linux 2023 AMI 2023.2.20231030.1 x86_64 HVM kernel-6.1'
region = regiones[actual]
session = boto3.Session(region_name=region,)
ec2 = session.client("ec2")
cloudformation = session.client("cloudformation")
# vpn_sg_id = ""
# ins_type = ""  ## tipo de instancia
# ami_id = ""
sg_stack_body = ""
vpn_stack_body = ""
sg_stack_path = "sg.yaml"   ### direccion del stack del security group
vpn_stack_path = "vpnstack.yaml"  ##direccion del stack de ec2
private_key = 'vpn.pem'   ### direccion de la private key

###guardar templates en variables
# def templates (sg_stack_path, vpn_stack_path):
#     global sg_stack_body, vpn_stack_body
#template sg
with open (sg_stack_path, "r") as sg_stack_file:
    sg_stack_body = sg_stack_file.read()
#template ec2
with open (vpn_stack_path, "r") as vpn_stack_file:
    vpn_stack_body = vpn_stack_file.read()

def seleccionar_region (reg):
    global ec2
    global cloudformation
    global actual
    actual = reg
    region = regiones[reg]
    session = boto3.Session(region_name=region,)
    ec2 = session.client("ec2")
    cloudformation = session.client("cloudformation")
##crear key par
def crearkeypar (keypub):
    keypairs = ec2.describe_key_pairs()
    keypar = next((key for key in keypairs['KeyPairs'] if key['KeyName']=='vpn'),None)
    # print(keypar)
    if keypar is None:
        response = ec2.import_key_pair(KeyName='vpn', PublicKeyMaterial=keypub)
        
########################################tipo de isntancia
##buscar tipo de instancia devulve el tipo de instancia
def buscar_tipo_instacia ():
    instancia = ""
    typei = [] 
    for a in instancetype:
        try:
            instancia = ec2.describe_instance_types(
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
def buscar_sgid ():
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}]) #obtener id vpc default
    default_vpc_id = vpcs["Vpcs"][0]["VpcId"]                                     #obtener id vpc default
    sgs = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])
    vpn_sg_id = next((sg for sg in sgs['SecurityGroups'] if sg['GroupName'] == "vpn_sg"), None)
    ##crear sg si no existe
    if vpn_sg_id is None:
        response = cloudformation.create_stack(
            StackName='sgVpn',
            TemplateBody=sg_stack_body,
            Parameters=[
                {'ParameterKey': "VpcId",'ParameterValue': default_vpc_id,},
            ],
            OnFailure='ROLLBACK',
        )
        waiter = cloudformation.get_waiter('stack_create_complete')
        waiter.wait(
            StackName=response['StackId'],
        )
        stack_descripcion = cloudformation.describe_stacks(StackName="sgVpn")
        return stack_descripcion["Stacks"][0]['Outputs'][0]['OutputValue']
        # print (vpn_sg_id)
    else:
        return vpn_sg_id['GroupId']
    # vpn_sg_id = [vpn_sg_id]
    print (vpn_sg_id)

#####################################ami id
#buscar ami id 
def buscar_amiid ():
    #global ami_id
    amis = ec2.describe_images(
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
    
def crear_stack (vpn_sg_id, ami_id, ins_type):
    response = cloudformation.create_stack(
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
    waiter = cloudformation.get_waiter('stack_create_complete')
    waiter.wait(
        StackName=response['StackId'],
    )
#     return response['StackId']


def buscar_stack ():
    stack_descripcion = cloudformation.describe_stacks()
    stack_vpn = next((st for st in stack_descripcion['Stacks'] if st['StackName'] == "ec2vpn"), None)
    # if stack_vpn == None:
    #     print("stack no creado")
    # else:
    #     print("stack ya creado")
    return stack_vpn

def eliminar_stack (waiter=True):
        cloudformation.delete_stack(StackName='ec2vpn',)
        if waiter:
            waiter_delete = cloudformation.get_waiter('stack_delete_complete')
            # stack_descripcion = cloudformation.describe_stacks()
            waiter_delete.wait(StackName='ec2vpn',)
        eliminar_conf()

def eliminar_conf(ruta=actual):
    direccion = f'./{ruta}.conf'
    try:
        os.remove(direccion)
        print(f"Archivo {direccion} eliminado exitosamente.")
    except OSError as e:
        print(f"Error al eliminar el archivo {direccion}: {e}")

def obtener_ip ():
    stack = buscar_stack()
    if stack == None:
        print("no creado")
        return stack
    else:
        ip = stack['Outputs'][0]['OutputValue']
        return ip

def extraer_conf(ip, region=region, intentos_maximos=3, tiempo_espera=60):
    source_path = f'ec2-user@{ip}:/home/wireguard/config/peer1/peer1.conf'
    destination_path = f'./{actual}.conf'

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
    # try:
    #     subprocess.run(scp_command, check=True)
    #     print("Transferencia exitosa")
    # except subprocess.CalledProcessError as e:
    #     print(f"Error en la transferencia: {e}")
        
def crear_vpn ():
    #condicional si no esta creado 
    vpn_sg_id = buscar_sgid()
    ami_id = buscar_amiid()
    ins_type = buscar_tipo_instacia()                     
    stack_vpn = buscar_stack ()
    
    if stack_vpn == None:
        stack = crear_stack(vpn_sg_id, ami_id, ins_type)
    else:
        #eliminado stack
        eliminar_stack ()
        #creando stack
        stack = crear_stack(vpn_sg_id, ami_id, ins_type)
    return stack
        
#### buscar todas las vpn
def buscar_todas ():
    las_regiones = {}
    for region in regiones:
        seleccionar_region(region)
        stack = buscar_stack()
        las_regiones[region] = stack
    return las_regiones

def apagar_todas():
    for region in regiones:
        seleccionar_region(region)
        stack = buscar_stack()
        if stack != None:
            eliminar_stack(False)
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

# regular_conf()
# seleccionar_region("us")
#crear_vpn()
# ip=obtener_ip()
# extraer_conf(ip)
# seleccionar_region("suecia")
# crear_vpn()
# ip=obtener_ip()
# extraer_conf(ip)
# apagar_todas()
# eliminar_conf("suecia")
# todas = buscar_todas()
# print(todas)