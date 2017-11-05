import chainer
import chainer.functions as F
from chainer import Variable

class Updater(chainer.training.StandardUpdater):
    def __init__(self, *args, **kwargs):
        self.gru, self.gen, self.image_dis, self.video_dis = kwargs.pop('models')
        self.T = kwargs.pop('video_length')
        self.img_size = kwargs.pop('img_size')
        super(Updater, self).__init__(*args, **kwargs)

    def loss_dis(self, dis, y_fake, y_real):
        batchsize = len(y_fake)
        L1 = F.sum(F.softplus(-y_real)) / batchsize
        L2 = F.sum(F.softplus(y_fake)) / batchsize
        loss = L1 + L2
        chainer.report({'loss': loss}, dis)
        return loss

    def loss_gru(self, gru, y_fake):
        batchsize = len(y_fake)
        loss = F.sum(F.softplus(-y_fake)) / batchsize
        chainer.report({'loss': loss}, gru)
        return loss

    def loss_gen(self, gen, y_fake):
        batchsize = len(y_fake)
        loss = F.sum(F.softplus(-y_fake)) / batchsize
        chainer.report({'loss': loss}, gen)
        return loss

    def update_core(self):
        gru_optimizer = self.get_optimizer('gru')
        gen_optimizer = self.get_optimizer('gen')
        image_dis_optimizer = self.get_optimizer('image_dis')
        video_dis_optimizer = self.get_optimizer('video_dis')

        gru, gen     = self.gru, self.gen
        image_dis, video_dis = self.image_dis, self.video_dis
        
        batch = self.get_iterator('main').next()
        batchsize = len(batch)
        
        ## real data
        x_real = Variable(self.converter(batch, self.device) / 255.)
        xp = chainer.cuda.get_array_module(x_real.data)
        y_real_i = image_dis(x_real[:,:,xp.random.randint(0, self.T)])
        y_real_v = video_dis(x_real)

        ## fake data
        zc = Variable(self.converter(gru.make_zc(batchsize), self.device))
        
        x_fake = xp.empty((self.T, batchsize, 3, self.img_size, self.img_size), dtype=xp.float32)
        for i in range(self.T):
        # for i in range(2):
            eps = Variable(self.converter(gru.make_zm(batchsize), self.device))
            zm = gru(eps).reshape(batchsize, gru.n_zm, 1, 1)
            z = xp.concatenate((zc.data, zm.data), axis=1)
            
            x_fake[i] = gen(z).data

        x_fake = x_fake.transpose(1, 2, 0, 3, 4)
        y_fake_i = image_dis(x_fake[:,:,xp.random.randint(0, self.T)])
        y_fake_v = video_dis(x_fake)
        y_fake = y_fake_i + y_fake_v.reshape(batchsize, 1, 1, 1)
        # import pdb; pdb.set_trace()
        
        ## update
        image_dis_optimizer.update(self.loss_dis, image_dis, y_fake_i, y_real_i)
        video_dis_optimizer.update(self.loss_dis, video_dis, y_fake_v, y_real_v)
        gru_optimizer.update(self.loss_gru, gru, y_fake)
        gen_optimizer.update(self.loss_gen, gen, y_fake)
